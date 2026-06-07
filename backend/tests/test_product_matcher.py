from datetime import date

from src.graph.state import DailyOutfit
from src.services.product_matcher import dedupe_by_iid, pick_top_n, score_product, to_product_card


def test_score_product_prefers_keyword_overlap() -> None:
    outfit = DailyOutfit(
        date=date(2026, 7, 10),
        outfit_summary="轻薄防晒衬衫 + 阔腿裤",
        search_keywords=["女 防晒 衬衫"],
    )
    good = {"title": "女夏季轻薄防晒衬衫", "price": "59", "sales": 0}
    bad = {"title": "男士皮鞋", "price": "59", "sales": 0}
    assert score_product(good, outfit, budget=200) > score_product(bad, outfit, budget=200)


def test_dedupe_by_iid() -> None:
    items = [
        {"num_iid": "1", "title": "a"},
        {"num_iid": "1", "title": "b"},
        {"num_iid": "2", "title": "c"},
    ]
    assert len(dedupe_by_iid(items)) == 2


def test_pick_top_n_returns_product_cards() -> None:
    outfit = DailyOutfit(
        date=date(2026, 7, 10),
        outfit_summary="防晒衬衫",
        search_keywords=["女 防晒 衬衫"],
    )
    candidates = [
        {
            "title": "女防晒衬衫夏季",
            "pic_url": "https://img.example/1.jpg",
            "price": "49.00",
            "detail_url": "https://item.taobao.com/item.htm?id=1",
            "num_iid": "1",
            "order_pay_uv": 5000,
        },
        {
            "title": "女白色防晒衬衫",
            "pic_url": "https://img.example/4.jpg",
            "price": "59.00",
            "detail_url": "https://item.taobao.com/item.htm?id=4",
            "num_iid": "4",
            "order_pay_uv": 3000,
        },
        {
            "title": "女轻薄防晒衬衫",
            "pic_url": "https://img.example/5.jpg",
            "price": "55.00",
            "detail_url": "https://item.taobao.com/item.htm?id=5",
            "num_iid": "5",
            "order_pay_uv": 2000,
        },
        {
            "title": "男皮鞋",
            "pic_url": "https://img.example/2.jpg",
            "price": "99.00",
            "detail_url": "https://item.taobao.com/item.htm?id=2",
            "num_iid": "2",
        },
    ]
    products = pick_top_n(candidates, outfit, n=3, budget=200)
    assert len(products) == 3
    assert products[0].num_iid == "1"
    assert all("皮鞋" not in product.title for product in products)


def test_to_product_card_skips_without_link() -> None:
    assert to_product_card({"title": "only title"}) is None


def test_to_product_card_marks_over_budget() -> None:
    card = to_product_card(
        {
            "title": "女 防晒 衬衫",
            "pic_url": "https://img.example/x.jpg",
            "price": "228",
            "detail_url": "https://item.taobao.com/item.htm?id=1",
        },
        max_price=200,
    )
    assert card is not None
    assert card.within_budget is False
