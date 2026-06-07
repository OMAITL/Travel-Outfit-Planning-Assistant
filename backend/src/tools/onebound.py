"""OneBound Taobao item search API client."""

from __future__ import annotations

import html
import re
from typing import Any

import time

import httpx

from src.config import get_settings
from src.services.api_recorder import record_api_exchange
from src.services.cache import cache_get, cache_set

ONEBOUND_SEARCH_URL = "https://api-gw.onebound.cn/taobao/item_search"
SUCCESS_CODES = {"0000", "2000"}
REQUEST_TIMEOUT = httpx.Timeout(connect=10.0, read=45.0, write=10.0, pool=10.0)
MAX_RETRIES = 2

ONEBOUND_ERROR_HINTS: dict[str, str] = {
    "4013": "OneBound 调用次数已超限，请登录 open.onebound.cn 充值或升级套餐后重试",
    "4005": "OneBound 密钥无效，请检查 backend/.env 中的 ONEBOUND_KEY / ONEBOUND_SECRET",
    "4016": "OneBound 账户余额不足，请充值后重试",
    "4014": "OneBound 接口权限不足，请确认套餐包含 item_search",
}


class OneBoundError(Exception):
    """Raised when OneBound returns a non-recoverable API error."""

    def __init__(self, message: str, *, error_code: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code


def _parse_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    items_block = data.get("items") or {}
    raw_items = items_block.get("item") or []
    if isinstance(raw_items, dict):
        raw_items = [raw_items]
    return [normalize_taobao_item(item) for item in raw_items if isinstance(item, dict)]


def normalize_taobao_pic_url(pic_url: str) -> str:
    """Convert Taobao/JustOne image paths to a fetchable img.alicdn.com URL."""
    pic_url = html.unescape(str(pic_url or "")).strip()
    if not pic_url:
        return ""
    if pic_url.startswith("//"):
        pic_url = f"https:{pic_url}"

    if re.search(r"search\d*\.alicdn\.com", pic_url, re.IGNORECASE):
        match = re.search(
            r"/uploaded/((?:i[1-4]/)+.+?\.(?:jpg|jpeg|png|webp|gif))",
            pic_url,
            re.IGNORECASE,
        )
        if match:
            path = match.group(1)
            while True:
                shard = re.match(r"^(i[1-4]/)(i[1-4]/)(.+)", path, re.IGNORECASE)
                if not shard or shard.group(1).lower() == shard.group(2).lower():
                    break
                path = f"{shard.group(2)}{shard.group(3)}"
            path = re.sub(r"^(i[1-4]/)\1", r"\1", path, flags=re.IGNORECASE)
            return f"https://img.alicdn.com/{path.split('?')[0]}"
        for marker in ("/uploaded/", "/imgextra/"):
            if marker in pic_url:
                tail = pic_url.split(marker, 1)[1].split("?")[0]
                tail = re.sub(r"^(i[1-4]/)\1", r"\1", tail, flags=re.IGNORECASE)
                if re.match(r"^i[1-4]/", tail, re.IGNORECASE):
                    return f"https://img.alicdn.com/{tail}"

    if pic_url.startswith(("http://", "https://")):
        return pic_url.split("?")[0]

    if re.match(r"^i[1-4]/", pic_url, re.IGNORECASE):
        return f"https://img.alicdn.com/{pic_url.split('?')[0]}"

    return pic_url


def normalize_taobao_item(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize OneBound / Taobao item fields for downstream ProductCard mapping."""
    normalized = dict(item)

    title = html.unescape(str(item.get("title") or "")).strip()
    title = re.sub(r"\s+", " ", title)
    normalized["title"] = title

    pic_url = str(
        item.get("pic_url") or item.get("pic") or item.get("thumbnail") or ""
    ).strip()
    normalized["pic_url"] = normalize_taobao_pic_url(pic_url)

    num_iid = item.get("num_iid")
    if num_iid is not None:
        normalized["num_iid"] = str(num_iid)
    detail_url = str(
        item.get("detail_url") or item.get("item_url") or item.get("url") or ""
    ).strip()
    if not detail_url and num_iid is not None:
        detail_url = f"https://item.taobao.com/item.htm?id={num_iid}"
    normalized["detail_url"] = detail_url

    price = item.get("promotion_price") or item.get("price") or item.get("orginal_price")
    normalized["price"] = price
    if item.get("promotion_price") is None:
        normalized["promotion_price"] = price

    return normalized


def _format_onebound_error(error_code: str, reason: str) -> str:
    hint = ONEBOUND_ERROR_HINTS.get(error_code)
    if hint:
        return f"{hint}（错误码 {error_code}）"
    return f"OneBound search failed ({error_code}): {reason}"


def search_taobao_items(
    keyword: str,
    max_price: float | None = None,
    page: int = 1,
    *,
    use_cache: bool = True,
) -> list[dict[str, Any]]:
    """Search Taobao items by keyword via OneBound API."""
    settings = get_settings()
    if not settings.onebound_key or not settings.onebound_secret:
        msg = "ONEBOUND_KEY / ONEBOUND_SECRET is not configured"
        raise ValueError(msg)

    keyword = keyword.strip()
    if not keyword:
        return []

    cache_params = {
        "keyword": keyword,
        "max_price": max_price,
        "page": page,
    }
    if use_cache:
        cached = cache_get("onebound_search", **cache_params)
        if cached is not None:
            return [normalize_taobao_item(item) for item in cached if isinstance(item, dict)]

    params: dict[str, Any] = {
        "key": settings.onebound_key,
        "secret": settings.onebound_secret,
        "q": keyword,
        "page": page,
        "start_price": 0,
        "end_price": max_price if max_price is not None else 0,
        "result_type": "json",
        "lang": "cn",
    }

    request_log = {
        "method": "GET",
        "url": ONEBOUND_SEARCH_URL,
        "params": {k: v for k, v in params.items() if k not in {"key", "secret"}},
    }
    started = time.perf_counter()
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            response = httpx.get(ONEBOUND_SEARCH_URL, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            break
        except httpx.TimeoutException as exc:
            last_error = exc
            if attempt + 1 >= MAX_RETRIES:
                record_api_exchange(
                    "taobao_onebound",
                    "item_search",
                    request_log,
                    status="error",
                    error=str(exc),
                    duration_ms=(time.perf_counter() - started) * 1000,
                    metadata={"attempt": attempt + 1},
                )
                raise OneBoundError(
                    "万邦 API 响应超时，请稍后重试（网络较慢时可减少行程天数或降低 ONEBOUND_MAX_CALLS_PER_RUN）",
                    error_code="timeout",
                ) from exc
        except httpx.HTTPError as exc:
            record_api_exchange(
                "taobao_onebound",
                "item_search",
                request_log,
                status="error",
                error=str(exc),
                duration_ms=(time.perf_counter() - started) * 1000,
            )
            raise OneBoundError(f"万邦 API 网络错误: {exc}", error_code="network") from exc
    else:
        if last_error is not None:
            raise OneBoundError(str(last_error), error_code="timeout") from last_error

    data = response.json()

    error_code = str(data.get("error_code", ""))
    if error_code not in SUCCESS_CODES:
        reason = str(data.get("reason") or data.get("error") or error_code)
        message = _format_onebound_error(error_code, reason)
        record_api_exchange(
            "taobao_onebound",
            "item_search",
            request_log,
            response=data,
            status="error",
            error=message,
            duration_ms=(time.perf_counter() - started) * 1000,
            metadata={"error_code": error_code},
        )
        raise OneBoundError(message, error_code=error_code)

    record_api_exchange(
        "taobao_onebound",
        "item_search",
        request_log,
        response=data,
        status="success",
        duration_ms=(time.perf_counter() - started) * 1000,
        metadata={"http_status": response.status_code},
    )

    items = _parse_items(data)
    if use_cache and items:
        cache_set("onebound_search", items, **cache_params)
    return items
