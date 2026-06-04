"""Tests for Just One API Taobao search client."""

from unittest.mock import patch

import httpx
import pytest

from src.tools.justoneapi import JustOneApiError, search_taobao_items

BASE = "https://api.justoneapi.com"
URL = f"{BASE}/api/taobao/search-item-list/v1"

SAMPLE_RESPONSE = {
    "code": "0",
    "message": "ok",
    "data": {
        "items": [
            {
                "itemId": "123456789",
                "title": "女夏季轻薄防晒衬衫",
                "mainImageUrl": "https://img.alicdn.com/example.jpg",
                "price": "59.00",
            }
        ]
    },
}

MODEL_RESPONSE = {
    "code": 0,
    "data": {
        "code": "SUCCESS",
        "model": {
            "itemList": [
                {
                    "itemId": "987654321",
                    "title": "轻薄防晒衣女",
                    "pic_url": "//img.alicdn.com/model.jpg",
                    "price": "88.00",
                    "auctionURL": "https://item.taobao.com/item.htm?id=987654321",
                }
            ]
        },
    },
}


def _json_response(data: dict) -> httpx.Response:
    request = httpx.Request("GET", URL)
    return httpx.Response(200, json=data, request=request)


def test_search_parses_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUSTONEAPI_TOKEN", "test-token")
    monkeypatch.setenv("PRODUCT_SOURCE", "justoneapi")
    from src.config import get_settings

    get_settings.cache_clear()

    with patch("src.tools.justone_client.httpx.get", return_value=_json_response(SAMPLE_RESPONSE)):
        with patch("src.tools.justoneapi.cache_get", return_value=None):
            with patch("src.tools.justoneapi.cache_set"):
                items = search_taobao_items("女 防晒 衬衫", max_price=200.0)

    get_settings.cache_clear()
    assert len(items) == 1
    assert items[0]["num_iid"] == "123456789"
    assert items[0]["detail_url"].startswith("https://item.taobao.com/")


def test_search_parses_model_item_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUSTONEAPI_TOKEN", "test-token")
    from src.config import get_settings

    get_settings.cache_clear()

    with patch("src.tools.justone_client.httpx.get", return_value=_json_response(MODEL_RESPONSE)):
        with patch("src.tools.justoneapi.cache_get", return_value=None):
            with patch("src.tools.justoneapi.cache_set"):
                items = search_taobao_items("防晒衣")

    get_settings.cache_clear()
    assert len(items) == 1
    assert items[0]["num_iid"] == "987654321"
    assert items[0]["pic_url"].startswith("https://")


def test_search_raises_on_quota(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUSTONEAPI_TOKEN", "test-token")
    from src.config import get_settings

    get_settings.cache_clear()

    err = {"code": "303", "message": "daily quota exceeded"}
    with patch("src.tools.justone_client.httpx.get", return_value=_json_response(err)):
        with patch("src.tools.justoneapi.cache_get", return_value=None):
            with pytest.raises(JustOneApiError) as exc_info:
                search_taobao_items("女装")
    get_settings.cache_clear()
    assert exc_info.value.error_code == "303"
