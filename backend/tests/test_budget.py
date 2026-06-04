"""Tests for category budget helpers."""

from src.graph.state import BudgetByCategory, TripPreferences
from src.services.budget import (
    budget_for_keyword,
    infer_item_category,
    normalize_budget_fields,
)


def test_infer_item_category() -> None:
    assert infer_item_category("女 白色 帆布鞋") == "shoes"
    assert infer_item_category("亚麻阔腿裤") == "bottom"
    assert infer_item_category("草编帽") == "acc"
    assert infer_item_category("防晒衬衫") == "top"


def test_budget_for_keyword_uses_category_cap() -> None:
    prefs = TripPreferences(
        budget_per_item=200,
        budget_by_category=BudgetByCategory(top=150, bottom=180, shoes=300, acc=80),
    )
    assert budget_for_keyword("帆布鞋", prefs) == 300
    assert budget_for_keyword("防晒T恤", prefs) == 150


def test_normalize_budget_fields_from_categories() -> None:
    per, total, bbc = normalize_budget_fields(
        budget_by_category={"top": 200, "bottom": 200, "shoes": 250, "acc": 150},
    )
    assert bbc is not None
    assert per == 250
    assert total == 800
