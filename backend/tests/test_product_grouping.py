"""Tests for outfit item parsing and product grouping."""

from datetime import date

from app.utils.enrichment import parse_outfit_items
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
        ),
        ProductCard(
            title="亚麻阔腿裤女夏季",
            pic_url="https://img.example/2.jpg",
            price=79.0,
            detail_url="https://item.taobao.com/item.htm?id=2",
            num_iid="2",
        ),
    ]
    groups = assign_products_to_items(outfit, products)
    assert len(groups) == 2
    assert len(groups[0][2]) >= 1
    assert len(groups[1][2]) >= 1
