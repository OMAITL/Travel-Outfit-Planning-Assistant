"""Tests for Just One API Xiaohongshu client."""

from unittest.mock import patch

import httpx
import pytest

from src.tools.justone_client import JustOneApiError
from src.tools.justone_xhs import fetch_outfit_inspirations, search_xhs_notes

BASE = "https://api.justoneapi.com"

SEARCH_RESPONSE = {
    "code": 0,
    "data": {
        "items": [
            {
                "note": {
                    "id": "abc123",
                    "title": "大理穿搭分享",
                    "type": "normal",
                    "images_list": [
                        {"url": "https://sns-img.example/cover.jpg"},
                    ],
                    "user": {"nickname": "旅行博主"},
                    "liked_count": 1200,
                }
            }
        ]
    },
}

DETAIL_RESPONSE = {
    "code": 0,
    "data": {
        "id": "abc123",
        "title": "大理穿搭分享",
        "images_list": [
            {"url": "https://sns-img.example/1.jpg"},
            {"url": "https://sns-img.example/2.jpg"},
        ],
    },
}


def _json_response(path: str, data: dict) -> httpx.Response:
    request = httpx.Request("GET", f"{BASE}{path}")
    return httpx.Response(200, json=data, request=request)


def test_search_xhs_notes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUSTONEAPI_TOKEN", "test-token")
    from src.config import get_settings

    get_settings.cache_clear()

    with patch(
        "src.tools.justone_client.httpx.get",
        return_value=_json_response("/api/xiaohongshu/search-note/v2", SEARCH_RESPONSE),
    ):
        notes = search_xhs_notes("大理 穿搭", use_cache=False)

    get_settings.cache_clear()
    assert len(notes) == 1
    assert notes[0].note_id == "abc123"
    assert notes[0].cover_url.startswith("https://")


def test_fetch_outfit_inspirations_with_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUSTONEAPI_TOKEN", "test-token")
    from src.config import get_settings

    get_settings.cache_clear()

    def fake_get(url: str, params=None, timeout=None):
        if "search-note" in url:
            return _json_response("/api/xiaohongshu/search-note/v2", SEARCH_RESPONSE)
        if "get-note-detail" in url:
            return _json_response("/api/xiaohongshu/get-note-detail/v2", DETAIL_RESPONSE)
        raise AssertionError(url)

    with patch("src.tools.justone_client.httpx.get", side_effect=fake_get):
        notes, calls = fetch_outfit_inspirations("大理 穿搭", max_notes=1, fetch_detail=True)

    get_settings.cache_clear()
    assert calls == 2
    assert len(notes) == 1
    assert len(notes[0].image_urls) >= 2


def test_search_raises_on_balance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUSTONEAPI_TOKEN", "test-token")
    from src.config import get_settings

    get_settings.cache_clear()

    err = {"code": "601", "message": "balance insufficient"}
    with patch(
        "src.tools.justone_client.httpx.get",
        return_value=_json_response("/api/xiaohongshu/search-note/v2", err),
    ):
        with pytest.raises(JustOneApiError) as exc_info:
            search_xhs_notes("穿搭", use_cache=False)
    get_settings.cache_clear()
    assert exc_info.value.error_code == "601"
