from unittest.mock import patch

import httpx

from src.tools.image_gen import build_outfit_prompt, generate_outfit_look

SUBMIT_RESPONSE = {
    "code": 10000,
    "data": {"task_id": "7392616336519610409"},
    "message": "Success",
}

DONE_RESPONSE = {
    "code": 10000,
    "data": {
        "status": "done",
        "image_urls": ["https://jimeng-result.example/outfit.png"],
    },
    "message": "Success",
}

PENDING_RESPONSE = {
    "code": 10000,
    "data": {"status": "generating"},
    "message": "Success",
}


def test_build_outfit_prompt_includes_context() -> None:
    prompt = build_outfit_prompt(
        destination="大理",
        date="2026-07-10",
        weather_summary="晴, 18~26°C",
        outfit_summary="防晒衬衫 + 阔腿裤",
        style="休闲",
        gender="女",
        activities=["拍照", "逛街"],
    )
    assert "大理" in prompt
    assert "防晒衬衫" in prompt
    assert "photo spot" in prompt or "scenic" in prompt


def test_generate_outfit_look_uses_jimeng(monkeypatch) -> None:
    monkeypatch.setenv("IMAGE_PROVIDER", "jimeng")
    monkeypatch.setenv("VOLCENGINE_ACCESS_KEY", "test-ak")
    monkeypatch.setenv("VOLCENGINE_SECRET_KEY", "test-sk")
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)

    from src.config import get_settings

    get_settings.cache_clear()

    call_count = {"n": 0}

    def mock_post(url, **kwargs):
        call_count["n"] += 1
        request = httpx.Request("POST", url)
        if "CVSync2AsyncSubmitTask" in url:
            return httpx.Response(200, json=SUBMIT_RESPONSE, request=request)
        return httpx.Response(200, json=DONE_RESPONSE, request=request)

    with patch("src.tools.jimeng.httpx.post", side_effect=mock_post):
        with patch("src.tools.jimeng.time.sleep"):
            url = generate_outfit_look("flat lay outfit")

    get_settings.cache_clear()
    assert url == "https://jimeng-result.example/outfit.png"
    assert call_count["n"] >= 1


def test_generate_outfit_look_returns_none_without_credentials(monkeypatch) -> None:
    monkeypatch.setenv("IMAGE_PROVIDER", "jimeng")

    from src.config import get_settings

    get_settings.cache_clear()

    with patch("src.tools.image_gen.generate_jimeng_image", return_value=None):
        with patch("src.tools.image_gen._generate_dashscope_look", return_value=None):
            assert generate_outfit_look("prompt") is None

    get_settings.cache_clear()
