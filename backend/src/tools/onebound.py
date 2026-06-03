"""OneBound Taobao item search API client."""

from __future__ import annotations

import html
import re
from typing import Any

import httpx

from src.config import get_settings
from src.services.cache import cache_get, cache_set

ONEBOUND_SEARCH_URL = "https://api-gw.onebound.cn/taobao/item_search"
SUCCESS_CODES = {"0000", "2000"}

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


def normalize_taobao_item(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize OneBound / Taobao item fields for downstream ProductCard mapping."""
    normalized = dict(item)

    title = html.unescape(str(item.get("title") or "")).strip()
    title = re.sub(r"\s+", " ", title)
    normalized["title"] = title

    pic_url = str(
        item.get("pic_url") or item.get("pic") or item.get("thumbnail") or ""
    ).strip()
    if pic_url.startswith("//"):
        pic_url = f"https:{pic_url}"
    elif pic_url and not pic_url.startswith(("http://", "https://")):
        pic_url = f"https://{pic_url.lstrip('/')}"
    normalized["pic_url"] = pic_url

    num_iid = item.get("num_iid")
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

    response = httpx.get(ONEBOUND_SEARCH_URL, params=params, timeout=15.0)
    response.raise_for_status()
    data = response.json()

    error_code = str(data.get("error_code", ""))
    if error_code not in SUCCESS_CODES:
        reason = str(data.get("reason") or data.get("error") or error_code)
        message = _format_onebound_error(error_code, reason)
        raise OneBoundError(message, error_code=error_code)

    items = _parse_items(data)
    if use_cache and items:
        cache_set("onebound_search", items, **cache_params)
    return items
