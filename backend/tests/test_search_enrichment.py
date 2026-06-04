"""Tests for search plan enrichment fallback."""

from datetime import date

from src.graph.state import BudgetByCategory, DailyOutfit, TripPreferences
from src.services.search_enrichment import enrich_search_plans


def test_enrich_search_plans_fallback_without_llm() -> None:
    outfit = DailyOutfit(
        date=date(2026, 6, 5),
        outfit_summary="上装：白色T恤 | 下装：蓝色牛仔裤 | 鞋：白色帆布鞋",
        search_keywords=["女 白色 T恤"],
    )
    prefs = TripPreferences(
        gender="女",
        style="休闲",
        height_cm=165,
        weight_kg=55,
        budget_by_category=BudgetByCategory(top=200, bottom=200, shoes=250, acc=150),
    )
    plans = enrich_search_plans([outfit], prefs, use_llm=False)
    assert len(plans) == 3
    assert plans[0].max_price == 200
    assert plans[2].max_price == 250
    assert "165" in plans[0].keyword or "M" in plans[0].keyword
