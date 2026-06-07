"""Just One API — Taobao/Tmall keyword search and item detail."""

from __future__ import annotations

import re
from typing import Any

from src.config import get_settings
from src.services.cache import cache_get, cache_set
from src.tools.justone_client import JustOneApiError, justone_get
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


def _resolve_search_price(raw: dict[str, Any]) -> float | None:
    """Extract sale price from Just One search-item-list v1 item fields."""
    for key in (
        "priceZKYuanDouble",
        "discntPriceYuan",
        "priceYuanDouble",
        "promotion_price",
        "couponPrice",
        "price",
        "zkFinalPrice",
        "viewPrice",
    ):
        value = raw.get(key)
        if value is not None and value != "":
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    for key, divisor in (("priceZKFen", 100), ("priceFen", 100)):
        value = raw.get(key)
        if value is not None and value != "":
            try:
                return float(value) / divisor
            except (TypeError, ValueError):
                continue
    price_show = raw.get("priceShow")
    if isinstance(price_show, dict) and price_show.get("price") is not None:
        try:
            return float(price_show["price"])
        except (TypeError, ValueError):
            pass
    return None


def _resolve_search_pic(raw: dict[str, Any]) -> str:
    """Prefer relative picUrl — picUrlFull often points at broken g.search.alicdn.com."""
    for key in (
        "picUrl",
        "pic_url",
        "pic",
        "mainImageUrl",
        "mainPic",
        "image",
        "img",
        "picUrlFull",
        "thumbnail",
    ):
        value = raw.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _parse_order_pay_uv(value: object) -> float:
    """Parse Just One orderPayUV like '1000+', '1万+', '少于100'."""
    if value is None or value == "":
        return 0.0
    text = str(value).strip().replace(",", "")
    if not text:
        return 0.0
    if "少于" in text or "小于" in text:
        return 50.0
    multiplier = 1.0
    if "万" in text:
        multiplier = 10000.0
        text = text.replace("万", "")
    text = text.replace("+", "").replace("人", "").strip()
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return 0.0
    try:
        return float(match.group(1)) * multiplier
    except ValueError:
        return 0.0


def _parse_comment_count(value: object) -> float:
    if value is None or value == "":
        return 0.0
    text = str(value).strip().replace(",", "")
    if "万" in text:
        match = re.search(r"(\d+(?:\.\d+)?)", text)
        if match:
            return float(match.group(1)) * 10000.0
    match = re.search(r"(\d+)", text)
    if match:
        return float(match.group(1))
    return 0.0


def _map_item(raw: dict[str, Any]) -> dict[str, Any]:
    num_iid = (
        raw.get("num_iid")
        or raw.get("itemId")
        or raw.get("item_id")
        or raw.get("id")
        or raw.get("nid")
    )
    title = (
        raw.get("title")
        or raw.get("itemName")
        or raw.get("itemTitle")
        or raw.get("name")
        or ""
    )
    pic = _resolve_search_pic(raw)
    price = _resolve_search_price(raw)
    detail_url = (
        raw.get("detail_url")
        or raw.get("detailUrl")
        or raw.get("itemUrl")
        or raw.get("auctionURL")
        or raw.get("url")
        or ""
    )
    sales = raw.get("realSales") or raw.get("volume") or raw.get("sales") or raw.get("sold")
    order_pay_uv = _parse_order_pay_uv(raw.get("orderPayUV") or raw.get("order_pay_uv"))
    comment_count = _parse_comment_count(raw.get("commentCount") or raw.get("comment_count"))
    seller_good_rating = raw.get("sellerGoodrat") or raw.get("seller_goodrat")
    return normalize_taobao_item(
        {
            "title": title,
            "pic_url": pic,
            "price": price,
            "promotion_price": price,
            "num_iid": num_iid,
            "detail_url": detail_url,
            "sales": sales,
            "order_pay_uv": order_pay_uv,
            "comment_count": comment_count,
            "seller_good_rating": seller_good_rating,
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
        end = int(max_price) if max_price == int(max_price) else round(max_price, 2)
        params["endPrice"] = str(end)

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
    if not raw_items and settings.justoneapi_sort == "bid":
        payload = justone_get(
            SEARCH_PATH,
            {**params, "sort": "_sale"},
            use_cache=False,
            cache_namespace=None,
            cache_params=None,
        )
        raw_items = _extract_raw_items(payload)
    if not raw_items and params.get("sort"):
        fallback_params = {k: v for k, v in params.items() if k != "sort"}
        payload = justone_get(
            SEARCH_PATH,
            fallback_params,
            use_cache=False,
            cache_namespace=None,
            cache_params=None,
        )
        raw_items = _extract_raw_items(payload)

    items = [_map_item(item) for item in raw_items]
    if use_cache and raw_items:
        cache_set("justoneapi_search", raw_items, **cache_params)
    return items
