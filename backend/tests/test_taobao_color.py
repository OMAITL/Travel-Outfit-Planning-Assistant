"""Tests for Taobao keyword color preservation and product color filtering."""

from src.services.product_matcher import (
    _title_conflicts_item_colors,
    _title_conflicts_item_materials,
    _title_conflicts_womens_item,
    pick_top_n,
)
from src.services.taobao_keyword import (
    build_item_search_keyword,
    ensure_keyword_has_item_colors,
    extract_color_phrases,
    extract_item_colors,
)
from src.graph.state import DailyOutfit


def test_build_item_search_keyword_includes_pink_and_blue() -> None:
    pink = build_item_search_keyword(
        "浅粉色宽松针织衫",
        gender="女",
        style="温柔",
        height_cm=165,
        weight_kg=90,
        body_type="微胖",
    )
    assert "浅粉色" in pink or "粉色" in pink

    blue = build_item_search_keyword(
        "深蓝色A字中长裙",
        gender="女",
        style="温柔",
        height_cm=165,
        weight_kg=90,
        body_type="微胖",
    )
    assert "深蓝" in blue or "蓝色" in blue


def test_ensure_keyword_has_item_colors_prepends_missing() -> None:
    keyword = ensure_keyword_has_item_colors("女 大码 A字中长裙", "深蓝色A字中长裙")
    assert "深蓝" in keyword


def test_title_conflicts_rejects_black_for_blue_skirt() -> None:
    assert _title_conflicts_item_colors("黑色高腰A字半身裙大码", "深蓝色A字中长裙")
    assert not _title_conflicts_item_colors("深蓝色A字半身裙大码", "深蓝色A字中长裙")


def test_beige_straw_bag_color_and_material_recognized() -> None:
    item = "米色草编挎包"
    assert "米色" in extract_color_phrases(item)
    assert "米" in extract_item_colors(item)
    keyword = build_item_search_keyword(item, gender="女", style="韩系")
    assert "米色" in keyword


def test_rejects_mens_waterproof_bag_for_beige_straw_bag() -> None:
    item = "米色草编挎包"
    title = "男士单肩休闲大容量多层防水单肩斜跨包"
    assert _title_conflicts_womens_item(title, item)
    assert _title_conflicts_item_materials(title, item)


def test_pick_top_n_prefers_beige_straw_bag() -> None:
    item_text = "米色草编挎包"
    outfit = DailyOutfit(
        date="2026-06-10",
        outfit_summary="配饰：米色草编挎包",
    )
    candidates = [
        {
            "title": "男士单肩休闲大容量多层防水单肩斜跨包",
            "pic_url": "https://img.example/a.jpg",
            "price": "30.01",
            "detail_url": "https://item.taobao.com/item.htm?id=1",
            "num_iid": "1",
            "sales": 9000,
        },
        {
            "title": "米色草编斜挎包女夏季海边度假小包",
            "pic_url": "https://img.example/b.jpg",
            "price": "45",
            "detail_url": "https://item.taobao.com/item.htm?id=2",
            "num_iid": "2",
            "sales": 300,
        },
        {
            "title": "无印良品 MUJI 纸编 斜挎包 米色",
            "pic_url": "https://img.example/c.jpg",
            "price": "40.8",
            "detail_url": "https://item.taobao.com/item.htm?id=3",
            "num_iid": "3",
            "sales": 500,
        },
    ]
    picked = pick_top_n(
        candidates,
        outfit,
        n=2,
        budget=150,
        category="acc",
        item_text=item_text,
        strict_budget=True,
    )
    assert len(picked) == 2
    assert all("男士" not in card.title for card in picked)
    assert all("防水" not in card.title or "米色" in card.title for card in picked)


def test_pick_top_n_prefers_matching_color() -> None:
    outfit = DailyOutfit(
        date="2026-06-10",
        outfit_summary="下装：深蓝色A字中长裙",
    )
    candidates = [
        {
            "title": "黑色高腰A字半身裙女大码梨形身材",
            "pic_url": "https://img.example/a.jpg",
            "price": "88.8",
            "detail_url": "https://item.taobao.com/item.htm?id=1",
            "num_iid": "1",
            "sales": 5000,
        },
        {
            "title": "深蓝色A字半身裙女夏季大码",
            "pic_url": "https://img.example/b.jpg",
            "price": "99",
            "detail_url": "https://item.taobao.com/item.htm?id=2",
            "num_iid": "2",
            "sales": 800,
        },
    ]
    picked = pick_top_n(
        candidates,
        outfit,
        n=1,
        category="bottom",
        item_text="深蓝色A字中长裙",
        strict_budget=False,
    )
    assert len(picked) == 1
    assert "深蓝" in picked[0].title
