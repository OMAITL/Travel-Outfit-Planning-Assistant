"""Shared HTTP client for Just One API endpoints."""

from __future__ import annotations

import time
from typing import Any

import httpx

from src.config import get_settings
from src.services.api_recorder import Provider, record_api_exchange

CN_BASE_URL = "http://47.117.133.51:30015"
REQUEST_TIMEOUT = httpx.Timeout(connect=15.0, read=90.0, write=15.0, pool=15.0)
SUCCESS_CODES = {"0", "200"}
RETRYABLE_CODES = {"301", "302"}
MAX_RETRIES = 2

JUSTONE_ERROR_HINTS: dict[str, str] = {
    "100": "Just One API Token 无效或已失效，请检查 JUSTONEAPI_TOKEN",
    "301": "Just One API 采集失败，请稍后重试",
    "302": "Just One API 超出速率限制，请降低调用频率",
    "303": "Just One API 超出每日配额",
    "400": "Just One API 参数错误",
    "500": "Just One API 内部服务器错误",
    "600": "Just One API 权限不足",
    "601": "Just One API 余额不足，请充值后重试",
}


class JustOneApiError(Exception):
    """Raised when Just One API returns a business error."""

    def __init__(self, message: str, *, error_code: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code


def _provider_for_path(path: str) -> Provider:
    lower = path.lower()
    if "xiaohongshu" in lower or "/xhs" in lower:
        return "xhs_justone"
    return "taobao_justone"


def format_justone_error(code: str, message: str, *, context: str = "request") -> str:
    hint = JUSTONE_ERROR_HINTS.get(code)
    if hint:
        return f"{hint}（错误码 {code}）"
    return f"Just One API {context} failed ({code}): {message}"


def justone_get(
    path: str,
    params: dict[str, Any],
    *,
    use_cache: bool = False,
    cache_namespace: str | None = None,
    cache_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """GET a Just One API endpoint with retry on 301/302."""
    settings = get_settings()
    token = settings.justoneapi_token
    if not token:
        msg = "JUSTONEAPI_TOKEN is not configured"
        raise ValueError(msg)

    if use_cache and cache_namespace and cache_params is not None:
        from src.services.cache import cache_get, cache_set

        cached = cache_get(cache_namespace, **cache_params)
        if isinstance(cached, dict):
            return cached

    base = settings.justoneapi_base_url.rstrip("/")
    url = f"{base}{path}"
    query = {"token": token, **params}

    provider = _provider_for_path(path)
    operation = path.strip("/").replace("/", "_") or "justone_request"
    request_log = {
        "method": "GET",
        "url": url,
        "path": path,
        "params": params,
    }

    last_error: Exception | None = None
    payload: dict[str, Any] | None = None
    started = time.perf_counter()
    for attempt in range(MAX_RETRIES + 1):
        if attempt > 0:
            time.sleep(3 * attempt)
        try:
            response = httpx.get(url, params=query, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            raw = response.json()
            if not isinstance(raw, dict):
                msg = f"Unexpected response type: {type(raw).__name__}"
                raise ValueError(msg)
            payload = raw
        except httpx.TimeoutException as exc:
            last_error = exc
            if attempt >= MAX_RETRIES:
                record_api_exchange(
                    provider,
                    operation,
                    request_log,
                    response=None,
                    status="error",
                    error=str(exc),
                    duration_ms=(time.perf_counter() - started) * 1000,
                    metadata={"attempt": attempt + 1},
                )
                raise JustOneApiError(
                    "Just One API 响应超时，请稍后重试或改用 JUSTONEAPI_BASE_URL 国内节点",
                    error_code="timeout",
                ) from exc
            continue
        except httpx.HTTPError as exc:
            record_api_exchange(
                provider,
                operation,
                request_log,
                response=None,
                status="error",
                error=str(exc),
                duration_ms=(time.perf_counter() - started) * 1000,
            )
            raise JustOneApiError(f"Just One API 网络错误: {exc}", error_code="network") from exc

        code = str(payload.get("code", ""))
        if code in SUCCESS_CODES:
            record_api_exchange(
                provider,
                operation,
                request_log,
                response=payload,
                status="success",
                duration_ms=(time.perf_counter() - started) * 1000,
                metadata={"attempt": attempt + 1, "http_status": response.status_code},
            )
            break
        if code not in RETRYABLE_CODES or attempt >= MAX_RETRIES:
            message = str(payload.get("message") or payload.get("msg") or code)
            record_api_exchange(
                provider,
                operation,
                request_log,
                response=payload,
                status="error",
                error=message,
                duration_ms=(time.perf_counter() - started) * 1000,
                metadata={"attempt": attempt + 1, "error_code": code},
            )
            raise JustOneApiError(format_justone_error(code, message), error_code=code)
    else:
        if last_error is not None:
            raise JustOneApiError(str(last_error), error_code="timeout") from last_error

    assert payload is not None
    if use_cache and cache_namespace and cache_params is not None:
        from src.services.cache import cache_set

        cache_set(cache_namespace, payload, **cache_params)

    return payload
