"""Tests for outfit item parsing and display sanitization."""

from app.utils.enrichment import (
    expand_outfit_item_slots,
    parse_outfit_items,
    sanitize_item_text_for_display,
    sanitize_recommendation_reason,
    split_compound_item_text,
)


def test_split_compound_keeps_paren_attributes_together() -> None:
    text = "白色短款修身T恤（圆领、短袖、露脐）"
    assert split_compound_item_text(text) == [text]


def test_split_compound_splits_real_accessory_lists() -> None:
    text = "宽檐草帽、民族风耳环、草编手提包"
    parts = split_compound_item_text(text)
    assert len(parts) == 3
    assert "草帽" in parts[0]


def test_expand_slots_does_not_break_paren_item() -> None:
    summary = "上装：白色短款修身T恤（圆领、短袖、露脐） | 下装：深灰色高腰不规则层叠半身长裙（垂坠感面料、前短后长设计）"
    slots = expand_outfit_item_slots(parse_outfit_items(summary))
    assert len(slots) == 2
    assert slots[0][1].startswith("白色短款修身T恤")
    assert "圆领" in slots[0][1]


def test_sanitize_item_strips_prompt_paren_hints() -> None:
    raw = "深灰色高腰不规则层叠半身长裙（垂坠感面料、前短后长设计）"
    assert sanitize_item_text_for_display(raw) == "深灰色高腰不规则层叠半身长裙"


def test_sanitize_item_strips_length_and_belt_hints() -> None:
    assert sanitize_item_text_for_display("深蓝色A字中长裙（及小腿）") == "深蓝色A字中长裙"
    assert sanitize_item_text_for_display("卡其色轻量防水风衣（系带收腰）") == "卡其色轻量防水风衣"


def test_sanitize_commerce_used_for_taobao_search() -> None:
    from src.services.taobao_keyword import simplify_item_for_search

    assert "及小腿" not in simplify_item_for_search("深蓝色A字中长裙（及小腿）")
    assert "系带" not in simplify_item_for_search("卡其色轻量防水风衣（系带收腰）")
    assert "A字" in simplify_item_for_search("深蓝色A字中长裙（及小腿）")


def test_sanitize_item_keeps_product_attribute_parens() -> None:
    raw = "白色短款修身T恤（圆领短袖露脐）"
    assert "圆领" in sanitize_item_text_for_display(raw)


def test_sanitize_recommendation_reason_strips_xhs_prefix() -> None:
    raw = "参考小红书「涩谷 女生 梨形 休闲 穿搭」高赞笔记，涩谷十字路口都市极简风正流行。"
    cleaned = sanitize_recommendation_reason(raw)
    assert "参考小红书" not in cleaned
    assert cleaned.startswith("涩谷十字路口")
