from unittest.mock import patch

import httpx
import pytest

from src.tools.jimeng import JimengError, generate_jimeng_image, get_task_result, submit_text_to_image_task

SUBMIT_RESPONSE = {
    "code": 10000,
    "data": {"task_id": "task-123"},
}

DONE_RESPONSE = {
    "code": 10000,
    "data": {
        "status": "done",
        "image_urls": ["https://jimeng.example/image.png"],
    },
}


def test_submit_text_to_image_task_returns_task_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOLCENGINE_ACCESS_KEY", "test-ak")
    monkeypatch.setenv("VOLCENGINE_SECRET_KEY", "test-sk")

    from src.config import get_settings

    get_settings.cache_clear()

    with patch("src.tools.jimeng.httpx.post") as mock_post:
        mock_post.return_value = httpx.Response(
            200,
            json=SUBMIT_RESPONSE,
            request=httpx.Request("POST", "https://example.com"),
        )
        task_id = submit_text_to_image_task("测试穿搭平铺图")

    get_settings.cache_clear()
    assert task_id == "task-123"


def test_generate_jimeng_image_polls_until_done(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOLCENGINE_ACCESS_KEY", "test-ak")
    monkeypatch.setenv("VOLCENGINE_SECRET_KEY", "test-sk")

    from src.config import get_settings

    get_settings.cache_clear()

    responses = [
        httpx.Response(200, json=SUBMIT_RESPONSE, request=httpx.Request("POST", "https://example.com")),
        httpx.Response(200, json={"code": 10000, "data": {"status": "generating"}}, request=httpx.Request("POST", "https://example.com")),
        httpx.Response(200, json=DONE_RESPONSE, request=httpx.Request("POST", "https://example.com")),
    ]

    with patch("src.tools.jimeng.httpx.post", side_effect=responses):
        with patch("src.tools.jimeng.time.sleep"):
            url = generate_jimeng_image("flat lay travel outfit")

    get_settings.cache_clear()
    assert url == "https://jimeng.example/image.png"


def test_get_task_result_raises_on_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOLCENGINE_ACCESS_KEY", "test-ak")
    monkeypatch.setenv("VOLCENGINE_SECRET_KEY", "test-sk")

    from src.config import get_settings

    get_settings.cache_clear()

    with patch("src.tools.jimeng.httpx.post") as mock_post:
        mock_post.return_value = httpx.Response(
            200,
            json={"code": 50412, "message": "Text Risk Not Pass"},
            request=httpx.Request("POST", "https://example.com"),
        )
        with pytest.raises(JimengError):
            get_task_result("task-123")

    get_settings.cache_clear()
