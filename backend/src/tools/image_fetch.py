"""Shared helpers to fetch external (XHS/Taobao) images as base64 / data URIs.

Server-side hotlink protection means these CDNs often reject direct fetches
without a browser-like User-Agent, so we download bytes locally and hand them
to downstream consumers (Jimeng i2i reference, multimodal Vision LLM).
"""

from __future__ import annotations

import base64

import httpx
from loguru import logger

DOWNLOAD_TIMEOUT = 25.0
DOWNLOAD_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


def xhs_friendly_image_url(url: str) -> str:
    """Prefer JPG and a moderate size — HEIF/large originals often fail downstream."""
    normalized = (url or "").strip()
    if not normalized:
        return normalized
    if "format/heif" in normalized:
        normalized = normalized.replace("format/heif", "format/jpg")
    if "/w/5000/" in normalized:
        normalized = normalized.replace("/w/5000/", "/w/1080/")
    if "/h/5000/" in normalized:
        normalized = normalized.replace("/h/5000/", "/h/1440/")
    return normalized


def download_image(url: str) -> tuple[bytes, str] | None:
    """Download an image; return (content, content_type) or None on failure."""
    friendly = xhs_friendly_image_url(url)
    if not friendly:
        return None
    try:
        with httpx.Client(timeout=DOWNLOAD_TIMEOUT, follow_redirects=True) as client:
            response = client.get(
                friendly,
                headers={"User-Agent": DOWNLOAD_USER_AGENT, "Accept": "image/*"},
            )
            response.raise_for_status()
            if not response.content:
                return None
            content_type = (response.headers.get("content-type") or "image/jpeg").split(";")[0]
            if not content_type.startswith("image/"):
                content_type = "image/jpeg"
            return response.content, content_type
    except httpx.HTTPError as exc:
        logger.warning("Image download failed: {} | {}", friendly[:120], exc)
        return None


def download_image_base64(url: str) -> str | None:
    """Download an image and return raw base64 (no data URI prefix)."""
    result = download_image(url)
    if result is None:
        return None
    content, _ = result
    return base64.b64encode(content).decode("ascii")


def download_image_data_uri(url: str) -> str | None:
    """Download an image and return a ``data:<mime>;base64,...`` URI for LLM input."""
    result = download_image(url)
    if result is None:
        return None
    content, content_type = result
    encoded = base64.b64encode(content).decode("ascii")
    return f"data:{content_type};base64,{encoded}"
