import pytest

from src.tools.product_search import ProductSearchError, search_products


def test_search_products_mock_source(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRODUCT_SOURCE", "mock")
    from src.config import get_settings

    get_settings.cache_clear()
    items = search_products("大理 防晒", use_cache=False)
    get_settings.cache_clear()
    assert len(items) >= 1
    assert "演示" in items[0]["title"] or items[0].get("detail_url")


def test_search_products_onebound_missing_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRODUCT_SOURCE", "onebound")
    monkeypatch.delenv("ONEBOUND_KEY", raising=False)
    monkeypatch.delenv("ONEBOUND_SECRET", raising=False)
    from src.config import reload_settings

    reload_settings()
    with pytest.raises((ProductSearchError, ValueError)):
        search_products("女装", use_cache=False)
