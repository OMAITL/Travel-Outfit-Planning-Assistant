"""Volcengine Jimeng AI text-to-image client (即梦文生图 3.1)."""

from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import urlencode

import httpx
from loguru import logger

from src.config import get_settings
from src.tools.volcengine_sign import HOST, VERSION, sign_request

API_BASE_URL = f"https://{HOST}/"
SUBMIT_ACTION = "CVSync2AsyncSubmitTask"
QUERY_ACTION = "CVSync2AsyncGetResult"
POLL_INTERVAL_SECONDS = 3.0
MAX_POLL_ATTEMPTS = 40


class JimengError(Exception):
    """Raised when Jimeng API returns a business error."""


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

    response = httpx.post(url, headers=headers, content=payload.encode(), timeout=30.0)
    response.raise_for_status()
    data = response.json()

    if data.get("code") != 10000:
        message = data.get("message") or data
        raise JimengError(f"Jimeng API error ({data.get('code')}): {message}")
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
        for _ in range(MAX_POLL_ATTEMPTS):
            result = get_task_result(task_id)
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
        body = ""
        if exc.response is not None:
            body = exc.response.text[:500]
        logger.warning("Jimeng HTTP error: {} | {}", exc, body)
        return None
