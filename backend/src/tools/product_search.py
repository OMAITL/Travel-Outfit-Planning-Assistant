"""Unified product search — OneBound API, experimental scraper, or mock fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import httpx

from src.config import BACKEND_ROOT, get_settings
from src.tools.justoneapi import JustOneApiError, search_taobao_items as justone_search
from src.tools.onebound import OneBoundError, search_taobao_items
from src.tools.taobao_scraper import TaobaoScraperError, search_taobao_items_scrape

ProductSource = Literal["onebound", "justoneapi", "scraper", "mock"]

_MOCK_FIXTURE = BACKEND_ROOT / "tests" / "fixtures" / "mock_products.json"


class ProductSearchError(Exception):
    """All configured product sources failed."""

    def __init__(self, message: str, *, source: str | None = None) -> None:
        super().__init__(message)
        self.source = source


def _load_mock_products(keyword: str) -> list[dict[str, Any]]:
    if not _MOCK_FIXTURE.exists():
        return []
    data = json.loads(_MOCK_FIXTURE.read_text(encoding="utf-8"))
    pools = data.get("pools") or {}
    default = data.get("default") or []
    key = keyword.strip().lower()
    for pool_key, items in pools.items():
        if pool_key in key or key in pool_key:
            return list(items)
    return list(default)


def search_products(
    keyword: str,
    max_price: float | None = None,
    page: int = 1,
    *,
    use_cache: bool = True,
) -> list[dict[str, Any]]:
    """
    Search Taobao products using ``PRODUCT_SOURCE`` from settings.

    - onebound: 万邦 aggregator API (key + secret)
    - justoneapi: Just One API token search
    - scraper: experimental HTML scrape (often blocked)
    - mock: local JSON fixture for demos without API quota
    """
    settings = get_settings()
    source = settings.product_source

    if source == "mock":
        return _load_mock_products(keyword)

    if source == "justoneapi":
        try:
            return justone_search(
                keyword,
                max_price=max_price,
                page=page,
                use_cache=use_cache,
            )
        except JustOneApiError as exc:
            raise ProductSearchError(str(exc), source="justoneapi") from exc

    if source == "scraper":
        try:
            return search_taobao_items_scrape(
                keyword,
                max_price=max_price,
                page=page,
                use_cache=use_cache,
            )
        except TaobaoScraperError as exc:
            raise ProductSearchError(str(exc), source="scraper") from exc

    # default: onebound
    try:
        return search_taobao_items(
            keyword,
            max_price=max_price,
            page=page,
            use_cache=use_cache,
        )
    except OneBoundError as exc:
        # Optional automatic fallback when quota exceeded
        if getattr(settings, "product_fallback_scraper", False) and exc.error_code == "4013":
            try:
                return search_taobao_items_scrape(
                    keyword,
                    max_price=max_price,
                    page=page,
                    use_cache=use_cache,
                )
            except TaobaoScraperError as scrape_exc:
                raise ProductSearchError(
                    f"OneBound quota exceeded; scraper fallback also failed: {scrape_exc}",
                    source="onebound",
                ) from scrape_exc
        raise ProductSearchError(str(exc), source="onebound") from exc
    except httpx.HTTPError as exc:
        raise ProductSearchError(f"商品搜索网络错误: {exc}", source="onebound") from exc
