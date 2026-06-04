"""Just One API — Taobao/Tmall keyword search and item detail."""

from __future__ import annotations

from typing import Any

from src.config import get_settings
from src.services.cache import cache_get, cache_set
from src.tools.justone_client import JustOneApiError, format_justone_error, justone_get
from src.tools.onebound import normalize_taobao_item

SEARCH_PATH = "/api/taobao/search-item-list/v1"
DETAIL_PATH = "/api/taobao/get-item-detail/v1"

# Re-export for backward compatibility
__all__ = ["JustOneApiError", "get_taobao_item_detail", "search_taobao_items"]


def _coerce_item_list(block: object) -> list[dict[str, Any]]:
    if isinstance(block, list):
        return [item for item in block if isinstance(item, dict)]
    if isinstance(block, dict):
        for key in ("items", "item", "list", "results", "data", "itemList"):
            nested = block.get(key)
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
            if isinstance(nested, dict):
                inner = nested.get("item")
                if isinstance(inner, list):
                    return [item for item in inner if isinstance(item, dict)]
                if isinstance(inner, dict):
                    return [inner]
    return []


def _extract_raw_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    if data is None:
        return []

    items = _coerce_item_list(data)
    if items:
        return items

    if isinstance(data, dict):
        model = data.get("model")
        if isinstance(model, dict):
            items = _coerce_item_list(model.get("itemList"))
            if items:
                return items

        for key in ("itemList", "searchResult", "resultList"):
            items = _coerce_item_list(data.get(key))
            if items:
                return items

    return []


def _map_item(raw: dict[str, Any]) -> dict[str, Any]:
    num_iid = (
        raw.get("num_iid")
        or raw.get("itemId")
        or raw.get("item_id")
        or raw.get("id")
        or raw.get("nid")
    )
    title = raw.get("title") or raw.get("itemTitle") or raw.get("name") or ""
    pic = (
        raw.get("pic_url")
        or raw.get("pic")
        or raw.get("mainImageUrl")
        or raw.get("mainPic")
        or raw.get("pic_path")
        or raw.get("image")
        or raw.get("img")
        or ""
    )
    price = (
        raw.get("promotion_price")
        or raw.get("couponPrice")
        or raw.get("price")
        or raw.get("zkFinalPrice")
        or raw.get("viewPrice")
        or raw.get("priceShow", {}).get("price")
        if isinstance(raw.get("priceShow"), dict)
        else None
    )
    detail_url = (
        raw.get("detail_url")
        or raw.get("detailUrl")
        or raw.get("itemUrl")
        or raw.get("auctionURL")
        or raw.get("url")
        or ""
    )
    return normalize_taobao_item(
        {
            "title": title,
            "pic_url": pic,
            "price": price,
            "promotion_price": price,
            "num_iid": num_iid,
            "detail_url": detail_url,
        }
    )


def _unwrap_detail_block(data: object) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    for key in ("item", "itemInfo", "model", "itemDetail"):
        nested = data.get(key)
        if isinstance(nested, dict):
            return nested
    return data


def get_taobao_item_detail(
    item_id: str,
    *,
    use_cache: bool = True,
) -> dict[str, Any] | None:
    """Fetch a single Taobao item via get-item-detail v1."""
    item_id = str(item_id).strip()
    if not item_id:
        return None

    cache_params = {"item_id": item_id}
    if use_cache:
        cached = cache_get("justoneapi_detail", **cache_params)
        if isinstance(cached, dict):
            return _map_item(cached)

    payload = justone_get(
        DETAIL_PATH,
        {"itemId": item_id},
        use_cache=False,
        cache_namespace=None,
        cache_params=None,
    )
    data = payload.get("data")
    block = _unwrap_detail_block(data)
    if not block:
        return None

    mapped = _map_item(block)
    if use_cache:
        cache_set("justoneapi_detail", block, **cache_params)
    return mapped


def search_taobao_items(
    keyword: str,
    max_price: float | None = None,
    page: int = 1,
    *,
    use_cache: bool = True,
) -> list[dict[str, Any]]:
    """Search Taobao items via Just One API search-item-list v1."""
    settings = get_settings()
    keyword = keyword.strip()
    if not keyword:
        return []

    cache_params = {
        "keyword": keyword,
        "max_price": max_price,
        "page": page,
        "sort": settings.justoneapi_sort,
    }
    if use_cache:
        cached = cache_get("justoneapi_search", **cache_params)
        if cached is not None:
            return [_map_item(item) for item in cached if isinstance(item, dict)]

    params: dict[str, Any] = {
        "keyword": keyword,
        "page": page,
        "sort": settings.justoneapi_sort,
    }
    if max_price is not None and max_price > 0:
        params["startPrice"] = "0"
        params["endPrice"] = str(int(max_price))

    try:
        payload = justone_get(
            SEARCH_PATH,
            params,
            use_cache=False,
            cache_namespace=None,
            cache_params=None,
        )
    except JustOneApiError:
        raise

    raw_items = _extract_raw_items(payload)
    items = [_map_item(item) for item in raw_items]
    if use_cache and raw_items:
        cache_set("justoneapi_search", raw_items, **cache_params)
    return items
