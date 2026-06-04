"""
Experimental Taobao search scraper (no official API).

WARNING — read before use:
- Taobao pages are heavily protected (login, CAPTCHA, JS). This module often returns
  empty results in production; it is for learning and last-resort fallback only.
- Scraping may violate Taobao's Terms of Service. Prefer OneBound, affiliate APIs,
  or mock/fixture data for coursework demos.
- Do not use at high frequency; add delays and respect platform rules.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any
from urllib.parse import quote_plus

import httpx

from src.config import get_settings
from src.services.cache import cache_get, cache_set
from src.tools.onebound import normalize_taobao_item

TAOBAO_SEARCH_URL = "https://s.taobao.com/search"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

# Simple rate limit between scrape requests (seconds)
_LAST_REQUEST_AT: float = 0.0


class TaobaoScraperError(Exception):
    """Raised when scraping fails or returns no parseable items."""

    def __init__(self, message: str, *, blocked: bool = False) -> None:
        super().__init__(message)
        self.blocked = blocked


def _rate_limit_wait(min_interval: float) -> None:
    global _LAST_REQUEST_AT
    now = time.monotonic()
    elapsed = now - _LAST_REQUEST_AT
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    _LAST_REQUEST_AT = time.monotonic()


def _extract_json_object_after_marker(html: str, marker: str) -> dict[str, Any] | None:
    """Extract a JSON object assigned to ``marker`` (e.g. g_page_config) via brace matching."""
    idx = html.find(marker)
    if idx < 0:
        return None
    start = html.find("{", idx)
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for pos in range(start, min(start + 2_000_000, len(html))):
        ch = html[pos]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                chunk = html[start : pos + 1]
                try:
                    data = json.loads(chunk)
                except json.JSONDecodeError:
                    return None
                return data if isinstance(data, dict) else None
    return None


def _auctions_from_g_page_config(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Walk common Taobao search page layouts for auction/item lists."""
    candidates: list[Any] = []

    mods = config.get("mods")
    if isinstance(mods, dict):
        itemlist = mods.get("itemlist")
        if isinstance(itemlist, dict):
            data = itemlist.get("data")
            if isinstance(data, dict):
                auctions = data.get("auctions")
                if isinstance(auctions, list):
                    candidates.extend(auctions)

    main = config.get("mainInfo")
    if isinstance(main, dict):
        for key in ("result", "items", "auctions"):
            block = main.get(key)
            if isinstance(block, list):
                candidates.extend(block)

    items_param = config.get("itemsArray")
    if isinstance(items_param, list):
        candidates.extend(items_param)

    return [item for item in candidates if isinstance(item, dict)]


def _auctions_from_embedded_scripts(html: str) -> list[dict[str, Any]]:
    """Try g_page_config and loose item.taobao.com patterns."""
    items: list[dict[str, Any]] = []

    config = _extract_json_object_after_marker(html, "g_page_config")
    if config:
        items.extend(_auctions_from_g_page_config(config))

    if items:
        return items

    # Fallback: item links with nearby title/price snippets (very fragile)
    for match in re.finditer(
        r'id["\']?\s*:\s*["\']?(\d{8,})["\']?',
        html,
    ):
        num_iid = match.group(1)
        items.append(
            {
                "num_iid": num_iid,
                "detail_url": f"https://item.taobao.com/item.htm?id={num_iid}",
                "title": "",
                "pic_url": "",
                "price": 0,
            }
        )
        if len(items) >= 20:
            break

    return items


def _map_auction_to_item(auction: dict[str, Any]) -> dict[str, Any]:
    """Map Taobao auction JSON fields to OneBound-like shape for normalize_taobao_item."""
    title = str(auction.get("title") or auction.get("raw_title") or "")
    title = re.sub(r"<[^>]+>", "", title)

    pic = str(
        auction.get("pic_url")
        or auction.get("pic")
        or auction.get("img")
        or auction.get("item_img")
        or ""
    )

    price = (
        auction.get("view_price")
        or auction.get("price")
        or auction.get("priceWap")
        or auction.get("promotion_price")
        or 0
    )
    if isinstance(price, str):
        price = price.replace("¥", "").strip()

    num_iid = auction.get("num_iid") or auction.get("nid") or auction.get("item_id")
    detail_url = str(auction.get("detail_url") or auction.get("url") or "")
    if not detail_url and num_iid is not None:
        detail_url = f"https://item.taobao.com/item.htm?id={num_iid}"

    return {
        "title": title,
        "pic_url": pic,
        "price": price,
        "promotion_price": price,
        "num_iid": str(num_iid) if num_iid is not None else None,
        "detail_url": detail_url,
    }


def _detect_block_page(html: str) -> bool:
    lowered = html.lower()
    block_signals = (
        "punish",
        "captcha",
        "validate",
        "login.taobao",
        "sessionkey",
        "请登录",
        "安全验证",
        "访问被拒绝",
    )
    return any(signal in lowered for signal in block_signals)


def _detect_spa_shell(html: str) -> bool:
    """
    Taobao PC search (2024+) returns a JS-rendered shell without embedded item JSON.

    Typical markers: ``<div id="root"></div>``, ``pc-search-2024``, skeleton DOM only.
    """
    if "g_page_config" in html or '"auctions"' in html:
        return False
    shell_markers = (
        'id="root"',
        "pc-search-2024",
        "boneClass_boneWrapper",
        "srp_hole_page",
    )
    return sum(1 for marker in shell_markers if marker in html) >= 2


def diagnose_scrape_response(html: str, *, final_url: str = "") -> dict[str, object]:
    """Return diagnostics for CLI/debug (no secrets)."""
    return {
        "html_length": len(html),
        "final_url": final_url,
        "blocked": _detect_block_page(html),
        "spa_shell": _detect_spa_shell(html),
        "has_g_page_config": "g_page_config" in html,
        "has_auctions": '"auctions"' in html or "auctions" in html,
        "has_item_links": "item.taobao.com" in html,
    }


def search_taobao_items_scrape(
    keyword: str,
    max_price: float | None = None,
    page: int = 1,
    *,
    use_cache: bool = True,
) -> list[dict[str, Any]]:
    """
    Scrape Taobao search results for ``keyword``.

    Returns normalized item dicts (same shape as OneBound after ``normalize_taobao_item``).
    Raises ``TaobaoScraperError`` when the page is blocked or unparsable.
    """
    settings = get_settings()
    keyword = keyword.strip()
    if not keyword:
        return []

    cache_params = {
        "keyword": keyword,
        "max_price": max_price,
        "page": page,
        "source": "scraper",
    }
    if use_cache:
        cached = cache_get("taobao_scrape", **cache_params)
        if cached is not None:
            return [normalize_taobao_item(item) for item in cached if isinstance(item, dict)]

    min_interval = max(0.0, float(getattr(settings, "scraper_min_interval_sec", 2.0)))
    _rate_limit_wait(min_interval)

    params = {"q": keyword, "page": page}
    headers = {
        "User-Agent": getattr(settings, "scraper_user_agent", None) or DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.taobao.com/",
    }

    try:
        response = httpx.get(
            TAOBAO_SEARCH_URL,
            params=params,
            headers=headers,
            timeout=20.0,
            follow_redirects=True,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        msg = f"Taobao scrape HTTP error: {exc}"
        raise TaobaoScraperError(msg) from exc

    html = response.text

    if _detect_block_page(html):
        raise TaobaoScraperError(
            "Taobao returned anti-bot or login page; scraping blocked. "
            "Use PRODUCT_SOURCE=mock or OneBound API instead.",
            blocked=True,
        )

    if len(html) < 500:
        raise TaobaoScraperError("Taobao scrape returned empty or truncated HTML")

    if _detect_spa_shell(html):
        raise TaobaoScraperError(
            "Taobao search page is a JavaScript SPA shell (pc-search-2024); "
            "product data is not in the HTML. httpx scraping cannot work here. "
            "Use PRODUCT_SOURCE=mock in .env, or restore OneBound API quota.",
            blocked=True,
        )

    raw_auctions = _auctions_from_embedded_scripts(html)
    if not raw_auctions:
        raise TaobaoScraperError(
            "Could not parse items from Taobao search HTML (no g_page_config / auctions). "
            "Page may require a real browser (Playwright) or an official API."
        )

    items: list[dict[str, Any]] = []
    for auction in raw_auctions:
        mapped = _map_auction_to_item(auction)
        title = str(mapped.get("title") or "").strip()
        if not title and not mapped.get("num_iid"):
            continue
        normalized = normalize_taobao_item(mapped)
        price = float(normalized.get("price") or 0)
        if max_price is not None and max_price > 0 and price > max_price:
            continue
        if not normalized.get("detail_url"):
            continue
        items.append(normalized)
        if len(items) >= 20:
            break

    if not items:
        raise TaobaoScraperError("Parsed Taobao page but no items passed filters.")

    if use_cache:
        cache_set("taobao_scrape", items, **cache_params)

    return items


def build_taobao_search_url(keyword: str) -> str:
    """Public search URL fallback when scrape/API both fail."""
    return f"{TAOBAO_SEARCH_URL}?q={quote_plus(keyword.strip())}"
