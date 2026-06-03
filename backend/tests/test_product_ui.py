"""Tests for product card UI helpers."""

from datetime import date

from app.components.product_card_item import _budget_status
from src.graph.state import ProductCard


def test_budget_status_within_budget() -> None:
    text, css_class = _budget_status(160, 200)
    assert "80" in text
    assert css_class == "good"


def test_budget_status_over_budget() -> None:
    text, css_class = _budget_status(250, 200)
    assert "超预算" in text
    assert css_class == "over"


def test_product_card_fields_match_onebound_shape() -> None:
    """Document the contract: live UI reads these ProductCard fields directly."""
    card = ProductCard(
        title="女夏季防晒衬衫",
        pic_url="https://img.alicdn.com/example.jpg",
        price=49.0,
        detail_url="https://item.taobao.com/item.htm?id=123",
        num_iid="123",
        trip_date=date(2026, 7, 10),
    )
    assert card.pic_url.startswith("https://")
    assert "item.taobao.com" in card.detail_url
