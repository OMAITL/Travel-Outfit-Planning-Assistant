from unittest.mock import patch

import httpx
import pytest

from src.tools.onebound import OneBoundError, normalize_taobao_item, search_taobao_items

ONEBOUND_URL = "https://api-gw.onebound.cn/taobao/item_search"

MOCK_RESPONSE = {
    "error_code": "0000",
    "items": {
        "item": [
            {
                "title": "轻薄防晒衬衫女夏季",
                "pic_url": "https://img.alicdn.com/example.jpg",
                "price": "59.00",
                "num_iid": "123456",
                "detail_url": "https://item.taobao.com/item.htm?id=123456",
                "sales": 100,
            }
        ]
    },
}


def _json_response(data: dict) -> httpx.Response:
    request = httpx.Request("GET", ONEBOUND_URL)
    return httpx.Response(200, json=data, request=request)


def test_search_taobao_items_parses_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ONEBOUND_KEY", "test-key")
    monkeypatch.setenv("ONEBOUND_SECRET", "test-secret")

    with patch("src.tools.onebound.httpx.get", return_value=_json_response(MOCK_RESPONSE)):
        with patch("src.tools.onebound.cache_get", return_value=None):
            with patch("src.tools.onebound.cache_set"):
                items = search_taobao_items("女 防晒 衬衫", max_price=200.0)

    assert len(items) == 1
    assert items[0]["num_iid"] == "123456"


def test_search_taobao_items_raises_on_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ONEBOUND_KEY", "test-key")
    monkeypatch.setenv("ONEBOUND_SECRET", "test-secret")

    error_response = {"error_code": "4013", "reason": "Number of calls exceeded"}
    with patch("src.tools.onebound.httpx.get", return_value=_json_response(error_response)):
        with patch("src.tools.onebound.cache_get", return_value=None):
            with pytest.raises(OneBoundError) as exc_info:
                search_taobao_items("女装")
    assert exc_info.value.error_code == "4013"
    assert "4013" in str(exc_info.value)


def test_normalize_taobao_pic_url_from_justone_recording() -> None:
    from src.tools.onebound import normalize_taobao_pic_url

    relative = "i4/2987571191/O1CN013srkaW1KfWqoai5mo_!!2987571191-0-scmitem176000.jpg"
    broken_full = (
        "https://g.search.alicdn.com/img/bao/uploaded/i4/i4/2987571191/"
        "O1CN013srkaW1KfWqoai5mo_!!2987571191-0-scmitem176000.jpg"
    )
    broken_search1 = (
        "https://g.search1.alicdn.com/img/bao/uploaded/i4/i2/2632725399/"
        "O1CN01A4cDMz1pknVFX50Qx_!!2632725399.jpg"
    )
    expected = f"https://img.alicdn.com/{relative}"
    expected_search1 = "https://img.alicdn.com/i2/2632725399/O1CN01A4cDMz1pknVFX50Qx_!!2632725399.jpg"
    assert normalize_taobao_pic_url(relative) == expected
    assert normalize_taobao_pic_url(broken_full) == expected
    assert normalize_taobao_pic_url(broken_search1) == expected_search1


def test_normalize_taobao_item_builds_urls() -> None:
    item = normalize_taobao_item(
        {
            "title": "  女&nbsp;防晒衬衫  ",
            "pic_url": "//img.alicdn.com/example.jpg",
            "price": "49.00",
            "num_iid": "123456",
        }
    )
    assert item["pic_url"].startswith("https://")
    assert item["detail_url"] == "https://item.taobao.com/item.htm?id=123456"
    assert "防晒" in item["title"]


def test_search_taobao_items_raises_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ONEBOUND_KEY", "test-key")
    monkeypatch.setenv("ONEBOUND_SECRET", "test-secret")

    with patch("src.tools.onebound.httpx.get", side_effect=httpx.ReadTimeout("timed out")):
        with patch("src.tools.onebound.cache_get", return_value=None):
            with pytest.raises(OneBoundError) as exc_info:
                search_taobao_items("女装", use_cache=False)
    assert exc_info.value.error_code == "timeout"


def test_search_taobao_items_uses_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ONEBOUND_KEY", "test-key")
    monkeypatch.setenv("ONEBOUND_SECRET", "test-secret")

    cached_items = [{"title": "cached", "pic_url": "x", "price": "1", "detail_url": "y"}]
    with patch("src.tools.onebound.cache_get", return_value=cached_items):
        with patch("src.tools.onebound.httpx.get") as mock_get:
            items = search_taobao_items("cached keyword")

    mock_get.assert_not_called()
    assert len(items) == 1
    assert items[0]["title"] == "cached"
    assert items[0]["pic_url"] == "x"
