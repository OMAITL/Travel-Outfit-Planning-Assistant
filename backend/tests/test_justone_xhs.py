"""Tests for Just One API Xiaohongshu client."""

from unittest.mock import patch

import httpx
import pytest

from src.tools.justone_client import JustOneApiError
from src.tools.justone_xhs import fetch_outfit_inspirations, get_xhs_note_detail, search_xhs_notes

BASE = "https://api.justoneapi.com"
SEARCH_PATH = "/api/xiaohongshu/search-note/v3"

SEARCH_RESPONSE = {
    "code": 0,
    "data": {
        "items": [
            {
                "model_type": "note",
                "note": {
                    "id": "abc123",
                    "title": "大理穿搭分享",
                    "type": "normal",
                    "images_list": [
                        {"url": "https://sns-img.example/cover.jpg"},
                    ],
                    "user": {"nickname": "旅行博主"},
                    "liked_count": 1200,
                },
            }
        ]
    },
}

DETAIL_RESPONSE = {
    "code": 0,
    "data": [
        {
            "model_type": "note",
            "note_list": [
                {
                    "id": "abc123",
                    "title": "大理穿搭分享",
                    "type": "normal",
                    "liked_count": 7310,
                    "images_list": [
                        {
                            "url": "https://sns-img.example/preview.jpg",
                            "original": "https://sns-img.example/1.jpg",
                        },
                        {
                            "url": "https://sns-img.example/2.jpg",
                        },
                    ],
                    "user": {"nickname": "旅行博主", "name": "旅行博主"},
                    "share_info": {
                        "link": "https://www.xiaohongshu.com/discovery/item/abc123?xsec_token=test",
                    },
                }
            ],
        }
    ],
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
        return_value=_json_response(SEARCH_PATH, SEARCH_RESPONSE),
    ):
        notes = search_xhs_notes("大理 穿搭", use_cache=False)

    get_settings.cache_clear()
    assert len(notes) == 1
    assert notes[0].note_id == "abc123"
    assert notes[0].cover_url.startswith("https://")
    assert notes[0].liked_count == 1200


def test_search_v3_uses_url_size_large_when_url_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUSTONEAPI_TOKEN", "test-token")
    from src.config import get_settings

    get_settings.cache_clear()

    payload = {
        "code": 0,
        "data": {
            "items": [
                {
                    "model_type": "note",
                    "note": {
                        "id": "img-fallback",
                        "title": "封面 fallback",
                        "type": "normal",
                        "images_list": [
                            {
                                "url": "",
                                "url_size_large": "https://sns-img.example/large.jpg",
                            }
                        ],
                    },
                }
            ]
        },
    }

    with patch(
        "src.tools.justone_client.httpx.get",
        return_value=_json_response(SEARCH_PATH, payload),
    ):
        notes = search_xhs_notes("穿搭", use_cache=False)

    get_settings.cache_clear()
    assert len(notes) == 1
    assert notes[0].cover_url == "https://sns-img.example/large.jpg"


def test_search_v3_video_cover_from_video_info(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUSTONEAPI_TOKEN", "test-token")
    from src.config import get_settings

    get_settings.cache_clear()

    payload = {
        "code": 0,
        "data": {
            "items": [
                {
                    "model_type": "note",
                    "note": {
                        "id": "video-note",
                        "desc": "视频穿搭分享",
                        "type": "video",
                        "images_list": [{"url": "https://sns-img.example/preview.jpg"}],
                        "video_info_v2": {
                            "image": {
                                "first_frame": "https://sns-img.example/frame.jpg",
                                "thumbnail": "https://sns-img.example/thumb.webp",
                            }
                        },
                    },
                }
            ]
        },
    }

    with patch(
        "src.tools.justone_client.httpx.get",
        return_value=_json_response(SEARCH_PATH, payload),
    ):
        notes = search_xhs_notes("穿搭", use_cache=False)

    get_settings.cache_clear()
    assert len(notes) == 1
    assert notes[0].note_id == "video-note"
    assert "https://sns-img.example/preview.jpg" in notes[0].image_urls
    assert "https://sns-img.example/frame.jpg" in notes[0].image_urls


def test_search_v3_skips_hot_query_and_ads_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUSTONEAPI_TOKEN", "test-token")
    from src.config import get_settings

    get_settings.cache_clear()

    payload = {
        "code": 0,
        "data": {
            "items": [
                {
                    "model_type": "hot_query",
                    "hot_query": {"queries": [{"name": "美食家常菜"}]},
                },
                {
                    "model_type": "ads",
                    "ads": {
                        "note": {
                            "id": "ad-note",
                            "title": "广告笔记",
                            "images_list": [{"url": "https://sns-img.example/ad.jpg"}],
                        }
                    },
                },
                {
                    "model_type": "note",
                    "note": {
                        "id": "real-note",
                        "title": "真实笔记",
                        "images_list": [{"url": "https://sns-img.example/real.jpg"}],
                    },
                },
            ]
        },
    }

    with patch(
        "src.tools.justone_client.httpx.get",
        return_value=_json_response(SEARCH_PATH, payload),
    ):
        notes = search_xhs_notes("穿搭", use_cache=False)

    get_settings.cache_clear()
    assert [n.note_id for n in notes] == ["real-note"]


def test_search_v3_includes_ads_when_requested(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUSTONEAPI_TOKEN", "test-token")
    from src.config import get_settings

    get_settings.cache_clear()

    payload = {
        "code": 0,
        "data": {
            "items": [
                {
                    "model_type": "ads",
                    "ads": {
                        "note": {
                            "id": "ad-note",
                            "title": "广告笔记",
                            "images_list": [{"url": "https://sns-img.example/ad.jpg"}],
                        }
                    },
                },
            ]
        },
    }

    with patch(
        "src.tools.justone_client.httpx.get",
        return_value=_json_response(SEARCH_PATH, payload),
    ):
        notes = search_xhs_notes("穿搭", include_ads=True, use_cache=False)

    get_settings.cache_clear()
    assert len(notes) == 1
    assert notes[0].note_id == "ad-note"


def test_get_xhs_note_detail_v2_note_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUSTONEAPI_TOKEN", "test-token")
    from src.config import get_settings

    get_settings.cache_clear()

    with patch(
        "src.tools.justone_client.httpx.get",
        return_value=_json_response("/api/xiaohongshu/get-note-detail/v2", DETAIL_RESPONSE),
    ):
        note = get_xhs_note_detail("abc123", use_cache=False)

    get_settings.cache_clear()
    assert note is not None
    assert note.note_id == "abc123"
    assert note.title == "大理穿搭分享"
    assert note.liked_count == 7310
    assert note.user_name == "旅行博主"
    assert note.note_url.startswith("https://www.xiaohongshu.com/discovery/item/abc123")
    assert len(note.image_urls) >= 2
    assert note.cover_url == "https://sns-img.example/1.jpg"


def test_fetch_outfit_inspirations_with_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUSTONEAPI_TOKEN", "test-token")
    from src.config import get_settings

    get_settings.cache_clear()

    def fake_get(url: str, params=None, timeout=None):
        if "search-note" in url:
            return _json_response(SEARCH_PATH, SEARCH_RESPONSE)
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
        return_value=_json_response(SEARCH_PATH, err),
    ):
        with pytest.raises(JustOneApiError) as exc_info:
            search_xhs_notes("穿搭", use_cache=False)
    get_settings.cache_clear()
    assert exc_info.value.error_code == "601"
