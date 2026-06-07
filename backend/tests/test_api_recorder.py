"""Tests for API request/response recording."""

import json

import pytest

from src.services import api_recorder


@pytest.fixture
def record_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("API_RECORD_ENABLED", "true")
    monkeypatch.setenv("API_RECORD_DIR", str(tmp_path / "recordings"))
    from src.config import get_settings

    get_settings.cache_clear()
    yield tmp_path / "recordings"
    get_settings.cache_clear()


def test_record_and_fetch_exchange(record_dir) -> None:
    record_id = api_recorder.record_api_exchange(
        "deepseek",
        "stylist_plan",
        request={"messages": [{"role": "user", "content": "hello"}]},
        response={"outfits": []},
        duration_ms=120.5,
    )
    assert record_id

    detail = api_recorder.get_recording(record_id)
    assert detail is not None
    assert detail["provider"] == "deepseek"
    assert detail["operation"] == "stylist_plan"
    assert detail["request"]["messages"][0]["content"] == "hello"


def test_sanitize_redacts_secrets(record_dir) -> None:
    record_id = api_recorder.record_api_exchange(
        "taobao_justone",
        "search",
        request={"token": "super-secret-token", "keyword": "连衣裙"},
        response={"code": "0"},
    )
    detail = api_recorder.get_recording(record_id)
    assert detail is not None
    assert "super-secret" not in json.dumps(detail["request"])
    assert detail["request"]["keyword"] == "连衣裙"


def test_find_recording_by_hash(record_dir) -> None:
    request = {"keyword": "白色连衣裙", "page": 1}
    api_recorder.record_api_exchange(
        "taobao_onebound",
        "item_search",
        request=request,
        response={"items": []},
    )
    found = api_recorder.find_recording("taobao_onebound", "item_search", request)
    assert found is not None
    assert found["response"] == {"items": []}


def test_disabled_when_api_record_enabled_false(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("API_RECORD_ENABLED", "false")
    monkeypatch.setenv("API_RECORD_DIR", str(tmp_path / "recordings"))
    from src.config import get_settings

    get_settings.cache_clear()
    record_id = api_recorder.record_api_exchange(
        "jimeng",
        "submit",
        request={"prompt": "test"},
        response={"ok": True},
    )
    get_settings.cache_clear()
    assert record_id is None
