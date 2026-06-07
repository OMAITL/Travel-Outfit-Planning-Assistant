"""Volcengine Jimeng AI text-to-image client (即梦文生图 3.1)."""

from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import urlencode

import httpx
from loguru import logger

from src.config import get_settings
from src.services.api_recorder import record_api_exchange
from src.tools.image_fetch import download_image_base64
from src.tools.image_fetch import xhs_friendly_image_url as _jimeng_friendly_image_url
from src.tools.volcengine_sign import HOST, VERSION, sign_request

API_BASE_URL = f"https://{HOST}/"
SUBMIT_ACTION = "CVSync2AsyncSubmitTask"
QUERY_ACTION = "CVSync2AsyncGetResult"
POLL_INTERVAL_SECONDS = 3.0
MAX_POLL_ATTEMPTS = 40


class JimengError(Exception):
    """Raised when Jimeng API returns a business error."""


def _http_error_body(exc: httpx.HTTPError) -> str:
    response = getattr(exc, "response", None)
    if response is None:
        return ""
    try:
        return response.text[:500]
    except Exception:
        return ""


def _download_reference_image_base64(url: str) -> str | None:
    """Download XHS CDN image locally; Jimeng often cannot fetch rednotecdn URLs."""
    return download_image_base64(url)


def _call_api(action: str, body: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    if not settings.volcengine_access_key or not settings.volcengine_secret_key:
        msg = "VOLCENGINE_ACCESS_KEY / VOLCENGINE_SECRET_KEY is not configured"
        raise ValueError(msg)

    query = {"Action": action, "Version": VERSION}
    payload = json.dumps(body, ensure_ascii=False)
    headers = sign_request(
        settings.volcengine_access_key,
        settings.volcengine_secret_key,
        method="POST",
        query=query,
        body=payload,
    )
    url = f"{API_BASE_URL}?{urlencode(query)}"
    request_log = {
        "method": "POST",
        "url": url,
        "action": action,
        "body": body,
    }
    started = time.perf_counter()

    try:
        response = httpx.post(url, headers=headers, content=payload.encode(), timeout=30.0)
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError as exc:
        record_api_exchange(
            "jimeng",
            action,
            request_log,
            status="error",
            error=str(exc),
            duration_ms=(time.perf_counter() - started) * 1000,
        )
        raise

    if data.get("code") != 10000:
        message = data.get("message") or data
        record_api_exchange(
            "jimeng",
            action,
            request_log,
            response=data,
            status="error",
            error=str(message),
            duration_ms=(time.perf_counter() - started) * 1000,
        )
        raise JimengError(f"Jimeng API error ({data.get('code')}): {message}")

    record_api_exchange(
        "jimeng",
        action,
        request_log,
        response=data,
        status="success",
        duration_ms=(time.perf_counter() - started) * 1000,
        metadata={"http_status": response.status_code},
    )
    return data


def submit_text_to_image_task(
    prompt: str,
    *,
    req_key: str | None = None,
    width: int | None = None,
    height: int | None = None,
    seed: int = -1,
    use_pre_llm: bool = False,
) -> str:
    """Submit an async Jimeng text-to-image task and return task_id."""
    settings = get_settings()
    body = {
        "req_key": req_key or settings.jimeng_req_key,
        "prompt": prompt,
        "seed": seed,
        "use_pre_llm": use_pre_llm,
        "width": width or settings.jimeng_image_width,
        "height": height or settings.jimeng_image_height,
    }
    data = _call_api(SUBMIT_ACTION, body)
    task_id = data.get("data", {}).get("task_id")
    if not task_id:
        raise JimengError(f"Missing task_id in submit response: {data}")
    return str(task_id)


def get_task_result(task_id: str, *, req_key: str | None = None) -> dict[str, Any]:
    """Query Jimeng async task status."""
    settings = get_settings()
    body = {
        "req_key": req_key or settings.jimeng_req_key,
        "task_id": task_id,
        "req_json": json.dumps(
            {
                "return_url": True,
                "logo_info": {"add_logo": False},
            },
            ensure_ascii=False,
        ),
    }
    return _call_api(QUERY_ACTION, body)


def submit_image_to_image_task(
    prompt: str,
    image_urls: list[str] | None = None,
    *,
    binary_data_base64: list[str] | None = None,
    req_key: str | None = None,
    seed: int = -1,
) -> str:
    """Submit an async Jimeng image-to-image task and return task_id."""
    if not image_urls and not binary_data_base64:
        msg = "image_urls or binary_data_base64 is required for image-to-image"
        raise ValueError(msg)
    settings = get_settings()
    body: dict[str, Any] = {
        "req_key": req_key or settings.jimeng_i2i_req_key,
        "prompt": prompt,
        "seed": seed,
    }
    if binary_data_base64:
        body["binary_data_base64"] = binary_data_base64
    else:
        body["image_urls"] = image_urls
    data = _call_api(SUBMIT_ACTION, body)
    task_id = data.get("data", {}).get("task_id")
    if not task_id:
        raise JimengError(f"Missing task_id in submit response: {data}")
    return str(task_id)


def _poll_jimeng_task(task_id: str, *, req_key: str | None = None) -> str | None:
    settings = get_settings()
    key = req_key or settings.jimeng_req_key
    for _ in range(MAX_POLL_ATTEMPTS):
        result = get_task_result(task_id, req_key=key)
        data = result.get("data") or {}
        status = data.get("status")

        if status == "done":
            urls = data.get("image_urls") or []
            return str(urls[0]) if urls else None

        if status in {"not_found", "expired"}:
            raise JimengError(f"Task {task_id} ended with status={status}")

        time.sleep(POLL_INTERVAL_SECONDS)

    msg = f"Jimeng task timed out: {task_id}"
    raise TimeoutError(msg)


def generate_jimeng_image_from_reference(prompt: str, reference_image_url: str) -> str | None:
    """Generate an image via Jimeng i2i using a reference outfit photo."""
    settings = get_settings()
    if not settings.volcengine_access_key or not settings.volcengine_secret_key:
        return None
    if not reference_image_url.strip():
        return None

    try:
        ref_b64 = _download_reference_image_base64(reference_image_url)
        if ref_b64:
            task_id = submit_image_to_image_task(
                prompt,
                binary_data_base64=[ref_b64],
                req_key=settings.jimeng_i2i_req_key,
            )
        else:
            task_id = submit_image_to_image_task(
                prompt,
                [_jimeng_friendly_image_url(reference_image_url)],
                req_key=settings.jimeng_i2i_req_key,
            )
        return _poll_jimeng_task(task_id, req_key=settings.jimeng_i2i_req_key)
    except JimengError as exc:
        logger.warning("Jimeng i2i API error: {}", exc)
        return None
    except TimeoutError as exc:
        logger.warning("{}", exc)
        return None
    except ValueError as exc:
        logger.warning("Jimeng i2i config error: {}", exc)
        return None
    except httpx.HTTPError as exc:
        logger.warning("Jimeng i2i HTTP error: {} | {}", exc, _http_error_body(exc))
        return None
    except Exception as exc:
        logger.warning("Jimeng i2i unexpected error: {}", exc)
        return None


def generate_jimeng_image(prompt: str) -> str | None:
    """
    Generate an image via Jimeng 3.1 and return the first image URL.

    Returns None on failure for graceful degradation in agent nodes.
    """
    settings = get_settings()
    if not settings.volcengine_access_key or not settings.volcengine_secret_key:
        return None

    try:
        task_id = submit_text_to_image_task(prompt)
        return _poll_jimeng_task(task_id)
    except JimengError as exc:
        logger.warning("Jimeng API error: {}", exc)
        return None
    except TimeoutError as exc:
        logger.warning("{}", exc)
        return None
    except ValueError as exc:
        logger.warning("Jimeng config error: {}", exc)
        return None
    except httpx.HTTPError as exc:
        logger.warning("Jimeng HTTP error: {} | {}", exc, _http_error_body(exc))
        return None
    except Exception as exc:
        logger.warning("Jimeng unexpected error: {}", exc)
        return None
