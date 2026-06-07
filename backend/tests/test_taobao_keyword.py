from src.services.product_matcher import color_match_score, popularity_score, score_product_for_item
from src.services.taobao_keyword import (
    build_item_search_keyword,
    extract_item_colors,
    simplify_item_for_search,
)


def test_simplify_item_keeps_color() -> None:
    assert "白色" in simplify_item_for_search("白色法式方领短款针织")
    assert simplify_item_for_search("米白色镂空针织背心") == "米白色镂空针织背心"


def test_simplify_item_keeps_short_text() -> None:
    assert simplify_item_for_search("德训鞋") == "德训鞋"


def test_build_item_search_keyword_includes_color() -> None:
    keyword = build_item_search_keyword("白色法式方领短袖针织", gender="女", style="休闲")
    assert "白色" in keyword
    assert "女" in keyword


def test_extract_item_colors() -> None:
    assert "白" in extract_item_colors("白色法式方领短款针织")
    assert "卡其" in extract_item_colors("卡其色高腰阔腿裤")


def test_color_match_score_penalizes_conflict() -> None:
    good = color_match_score("女白色法式方领短袖针织", "白色法式方领短款针织")
    bad = color_match_score("专柜薄荷绿法式方领短袖针织", "白色法式方领短款针织")
    assert good > bad


def test_popularity_score_prefers_higher_sales() -> None:
    low = popularity_score({"order_pay_uv": 50})
    high = popularity_score({"order_pay_uv": 5000, "comment_count": 2000})
    assert high > low


def test_score_product_for_item_prefers_color_and_popularity() -> None:
    white = score_product_for_item(
        {
            "title": "女白色法式方领短袖针织T恤",
            "price": 69,
            "order_pay_uv": 3000,
        },
        item_text="白色法式方领短款针织",
        budget=200,
    )
    green = score_product_for_item(
        {
            "title": "专柜薄荷绿法式方领短袖针织",
            "price": 69,
            "order_pay_uv": 8000,
        },
        item_text="白色法式方领短款针织",
        budget=200,
    )
    assert white > green
