from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from src.tools.taobao_scraper import (
    TaobaoScraperError,
    _auctions_from_embedded_scripts,
    _detect_spa_shell,
    build_taobao_search_url,
    search_taobao_items_scrape,
)

FIXTURE_HTML = Path(__file__).parent / "fixtures" / "taobao_search_sample.html"


def test_parse_sample_html_fixture() -> None:
    html = FIXTURE_HTML.read_text(encoding="utf-8")
    auctions = _auctions_from_embedded_scripts(html)
    assert len(auctions) >= 2


def test_search_scrape_parses_mock_response(monkeypatch: pytest.MonkeyPatch) -> None:
    html = FIXTURE_HTML.read_text(encoding="utf-8")
    request = httpx.Request("GET", "https://s.taobao.com/search")
    response = httpx.Response(200, text=html, request=request)

    monkeypatch.setenv("SCRAPER_MIN_INTERVAL_SEC", "0")

    with patch("src.tools.taobao_scraper.httpx.get", return_value=response):
        with patch("src.tools.taobao_scraper.cache_get", return_value=None):
            with patch("src.tools.taobao_scraper.cache_set"):
                items = search_taobao_items_scrape("女 防晒 衬衫", use_cache=False)

    assert len(items) >= 2
    assert items[0]["title"]
    assert items[0]["detail_url"].startswith("https://")


def test_search_scrape_raises_on_block_page(monkeypatch: pytest.MonkeyPatch) -> None:
    html = "<html><body>请登录淘宝安全验证 captcha</body></html>"
    request = httpx.Request("GET", "https://s.taobao.com/search")
    response = httpx.Response(200, text=html, request=request)
    monkeypatch.setenv("SCRAPER_MIN_INTERVAL_SEC", "0")

    with patch("src.tools.taobao_scraper.httpx.get", return_value=response):
        with patch("src.tools.taobao_scraper.cache_get", return_value=None):
            with pytest.raises(TaobaoScraperError) as exc_info:
                search_taobao_items_scrape("女装", use_cache=False)
    assert exc_info.value.blocked is True


def test_build_search_url() -> None:
    url = build_taobao_search_url("女 防晒 衬衫")
    assert "s.taobao.com/search" in url
    assert "%E5%A5%B3" in url or "q=" in url


def test_detect_spa_shell_on_modern_taobao_page() -> None:
    html = FIXTURE_HTML.read_text(encoding="utf-8")
    # Sample fixture has g_page_config — not SPA
    assert _detect_spa_shell(html) is False

    spa_html = '<div id="root"></div><script>pc-search-2024</script><div class="boneClass_boneWrapper">'
    assert _detect_spa_shell(spa_html) is True


def test_search_scrape_raises_on_spa_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    spa_html = (
        "<html><body><div id=\"root\"></div>"
        "<script>main-search/pc-search-2024/1.8.44</script>"
        "<div class=\"boneClass_boneWrapper\"></div>"
        + "x" * 600
        + "</body></html>"
    )
    request = httpx.Request("GET", "https://s.taobao.com/search")
    response = httpx.Response(200, text=spa_html, request=request)
    monkeypatch.setenv("SCRAPER_MIN_INTERVAL_SEC", "0")

    with patch("src.tools.taobao_scraper.httpx.get", return_value=response):
        with patch("src.tools.taobao_scraper.cache_get", return_value=None):
            with pytest.raises(TaobaoScraperError) as exc_info:
                search_taobao_items_scrape("女装", use_cache=False)
    assert exc_info.value.blocked is True
    assert "SPA" in str(exc_info.value) or "JavaScript" in str(exc_info.value)
