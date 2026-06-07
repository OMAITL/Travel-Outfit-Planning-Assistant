from datetime import date

from src.graph.state import BudgetByCategory, DailyOutfit, TripPreferences
from src.services.search_enrichment import ShoppingSearchItem, _dedupe_search_plans, enrich_search_plans


def test_dedupe_search_plans_by_date_label_and_item_text() -> None:
    plans = [
        ShoppingSearchItem(
            date=date(2026, 6, 5),
            label="配饰",
            item_text="宽檐草帽",
            keyword="女 草帽",
            category="acc",
            max_price=150,
        ),
        ShoppingSearchItem(
            date=date(2026, 6, 5),
            label="配饰",
            item_text="草编手提包",
            keyword="女 草编包",
            category="acc",
            max_price=150,
        ),
        ShoppingSearchItem(
            date=date(2026, 6, 5),
            label="配饰",
            item_text="宽檐草帽",
            keyword="女 草帽 duplicate",
            category="acc",
            max_price=150,
        ),
    ]
    assert len(_dedupe_search_plans(plans)) == 2


def test_compound_accessories_expand_to_multiple_plans() -> None:
    outfits = [
        DailyOutfit(
            date=date(2026, 6, 5),
            outfit_summary="上装：白T | 配饰：宽檐草帽、民族风耳环、草编手提包",
            search_keywords=[],
        ),
    ]
    prefs = TripPreferences(
        budget_by_category=BudgetByCategory(top=200, bottom=200, shoes=250, acc=150),
    )
    plans = enrich_search_plans(outfits, prefs, use_llm=False)
    assert len(plans) == 4
    acc_plans = [plan for plan in plans if plan.category == "acc"]
    assert len(acc_plans) == 3
    assert {plan.item_text for plan in acc_plans} == {"宽檐草帽", "民族风耳环", "草编手提包"}


def test_enrich_search_plans_respects_outfit_slot_count() -> None:
    outfits = [
        DailyOutfit(
            date=date(2026, 6, 5),
            outfit_summary="上装：白T | 下装：牛仔裤 | 鞋：帆布鞋",
            search_keywords=[],
        ),
        DailyOutfit(
            date=date(2026, 6, 6),
            outfit_summary="上装：衬衫 | 下装：短裤 | 鞋：凉鞋",
            search_keywords=[],
        ),
    ]
    prefs = TripPreferences(
        budget_by_category=BudgetByCategory(top=200, bottom=200, shoes=250, acc=150),
    )
    plans = enrich_search_plans(outfits, prefs, use_llm=False)
    assert len(plans) == 6
