"""Tests for outfit item parsing and product grouping."""

from datetime import date

from app.utils.enrichment import expand_outfit_item_slots, parse_outfit_items, split_compound_item_text
from app.utils.product_grouping import assign_products_to_items
from src.graph.state import DailyOutfit, ProductCard


def test_parse_outfit_items_pipe_format() -> None:
    summary = (
        "上装：白色蕾丝短袖上衣 | 下装：淡蓝色碎花半身裙 | "
        "鞋：白色帆布鞋 | 配饰：草帽 | 包：藤编小包"
    )
    items = parse_outfit_items(summary)
    assert len(items) == 5
    assert items[0] == ("上装", "白色蕾丝短袖上衣")
    assert items[1] == ("下装", "淡蓝色碎花半身裙")


def test_split_compound_item_text() -> None:
    assert split_compound_item_text("宽檐草帽、民族风耳环、草编手提包") == [
        "宽檐草帽",
        "民族风耳环",
        "草编手提包",
    ]


def test_expand_outfit_item_slots() -> None:
    parsed = parse_outfit_items("上装：白T | 配饰：宽檐草帽、草编手提包")
    expanded = expand_outfit_item_slots(parsed)
    assert expanded == [
        ("上装", "白T"),
        ("配饰", "宽檐草帽"),
        ("配饰", "草编手提包"),
    ]


def test_assign_products_to_items() -> None:
    outfit = DailyOutfit(
        date=date(2026, 6, 10),
        outfit_summary="上装：防晒衬衫 | 下装：亚麻阔腿裤",
        search_keywords=["女 防晒 衬衫", "女 亚麻 阔腿裤"],
    )
    products = [
        ProductCard(
            title="女夏季防晒衬衫轻薄",
            pic_url="https://img.example/1.jpg",
            price=49.0,
            detail_url="https://item.taobao.com/item.htm?id=1",
            num_iid="1",
            item_text="防晒衬衫",
            category="top",
        ),
        ProductCard(
            title="亚麻阔腿裤女夏季",
            pic_url="https://img.example/2.jpg",
            price=79.0,
            detail_url="https://item.taobao.com/item.htm?id=2",
            num_iid="2",
            item_text="亚麻阔腿裤",
            category="bottom",
        ),
        ProductCard(
            title="复古平底凉鞋女",
            pic_url="https://img.example/3.jpg",
            price=58.0,
            detail_url="https://item.taobao.com/item.htm?id=3",
            num_iid="3",
            item_text="棕色复古平底凉鞋",
            category="shoes",
        ),
    ]
    groups = assign_products_to_items(outfit, products)
    assert len(groups) == 2
    assert groups[0][2][0].title.startswith("女夏季防晒")
    assert groups[1][2][0].title.startswith("亚麻阔腿裤")
    assert all("凉鞋" not in product.title for product in groups[0][2])


def test_assign_products_strict_no_accessory_in_skirt_group() -> None:
    # Req 3: an accessory (hat) must never appear under a 下装(裙) slot.
    outfit = DailyOutfit(
        date=date(2026, 6, 7),
        outfit_summary="下装：蓝白扎染半身长裙 | 配饰：宽檐草帽",
        search_keywords=["女 蓝白 半身裙", "女 宽檐 草帽"],
    )
    products = [
        ProductCard(
            title="2026夏季海洋系蓝白扎染半身裙女长裙",
            pic_url="https://img.example/1.jpg",
            price=188.0,
            detail_url="https://item.taobao.com/item.htm?id=1",
            num_iid="1",
            item_text="蓝白扎染半身长裙",
            category="bottom",
        ),
        ProductCard(
            title="栀野经典白色巴拿马草帽女遮阳帽",
            pic_url="https://img.example/2.jpg",
            price=84.1,
            detail_url="https://item.taobao.com/item.htm?id=2",
            num_iid="2",
            item_text="宽檐草帽",
            category="acc",
        ),
    ]
    groups = assign_products_to_items(outfit, products)
    by_label = {label: prods for label, _text, prods in groups}
    assert all("帽" not in p.title for p in by_label["下装"])
    assert by_label["下装"] and by_label["下装"][0].num_iid == "1"
    assert by_label["配饰"] and by_label["配饰"][0].num_iid == "2"
