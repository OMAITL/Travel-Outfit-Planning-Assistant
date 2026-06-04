"""Product matching and ranking for Shopping Agent."""

from __future__ import annotations

import re
from typing import Any

from src.graph.state import DailyOutfit, ProductCard
from src.services.budget import infer_item_category


def _tokenize(text: str) -> set[str]:
    tokens: set[str] = set()
    for chunk in re.split(r"\s+", text.strip()):
        if not chunk:
            continue
        tokens.add(chunk.lower())
        if re.search(r"[\u4e00-\u9fff]", chunk):
            tokens.update(char for char in chunk if "\u4e00" <= char <= "\u9fff")
    return tokens


def _keyword_hits(title: str, outfit: DailyOutfit) -> float:
    hits = 0.0
    for keyword in outfit.search_keywords:
        for part in keyword.split():
            part = part.strip()
            if part and part in title:
                hits += 1.0
    for token in _tokenize(outfit.outfit_summary):
        if len(token) >= 2 and token in title.lower():
            hits += 0.5
    return hits


def _parse_price(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def score_product(
    item: dict[str, Any],
    outfit: DailyOutfit,
    budget: float | None = None,
) -> float:
    """Score a Taobao item against a daily outfit plan."""
    title = str(item.get("title") or "")
    title_lower = title.lower()
    title_tokens = _tokenize(title)

    keyword_tokens: set[str] = set()
    for keyword in outfit.search_keywords:
        keyword_tokens |= _tokenize(keyword)
    keyword_tokens |= _tokenize(outfit.outfit_summary)

    overlap = len(title_tokens & keyword_tokens)
    score = overlap * 10.0 + _keyword_hits(title_lower, outfit) * 10.0

    price = _parse_price(item.get("promotion_price") or item.get("price"))
    if budget is not None and budget > 0:
        if price <= budget:
            score += 5.0
        elif price <= budget * 1.05:
            score += 1.0
        else:
            score -= 50.0

    sales = item.get("sales")
    if isinstance(sales, (int, float)) and sales > 0:
        score += min(float(sales) / 1000.0, 3.0)

    return score


def dedupe_by_iid(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in items:
        iid = str(item.get("num_iid") or "")
        if iid and iid in seen:
            continue
        if iid:
            seen.add(iid)
        unique.append(item)
    return unique


def to_product_card(
    item: dict[str, Any],
    trip_date=None,
    *,
    category: str | None = None,
    item_label: str | None = None,
    item_text: str | None = None,
    max_price: float | None = None,
    size_hint: str | None = None,
) -> ProductCard | None:
    from src.tools.onebound import normalize_taobao_item

    item = normalize_taobao_item(item)
    title = str(item.get("title") or "").strip()
    pic_url = str(item.get("pic_url") or "").strip()
    detail_url = str(item.get("detail_url") or "").strip()
    if not title:
        return None
    if not pic_url:
        pic_url = "https://via.placeholder.com/300?text=No+Image"
    if not detail_url:
        num_iid = item.get("num_iid")
        if num_iid is not None:
            detail_url = f"https://item.taobao.com/item.htm?id={num_iid}"
        else:
            return None

    num_iid = item.get("num_iid")
    inferred = category or infer_item_category(title)
    if inferred not in ("top", "bottom", "shoes", "acc"):
        inferred = "top"
    price = _parse_price(item.get("promotion_price") or item.get("price"))
    within = True
    if max_price is not None and max_price > 0:
        within = price <= max_price
    return ProductCard(
        title=title,
        pic_url=pic_url,
        price=price,
        detail_url=detail_url,
        num_iid=str(num_iid) if num_iid is not None else None,
        trip_date=trip_date,
        category=inferred,  # type: ignore[arg-type]
        item_label=item_label,
        item_text=item_text,
        within_budget=within,
        size_hint=size_hint,
    )


def pick_top_n(
    candidates: list[dict[str, Any]],
    outfit: DailyOutfit,
    n: int = 3,
    budget: float | None = None,
    *,
    category: str | None = None,
    item_label: str | None = None,
    item_text: str | None = None,
    size_hint: str | None = None,
    strict_budget: bool = True,
) -> list[ProductCard]:
    """Deduplicate, score, and return top N product cards within budget."""
    ranked = sorted(
        dedupe_by_iid(candidates),
        key=lambda item: score_product(item, outfit, budget),
        reverse=True,
    )

    products: list[ProductCard] = []
    for item in ranked:
        price = _parse_price(item.get("promotion_price") or item.get("price"))
        if strict_budget and budget is not None and budget > 0 and price > budget:
            continue
        card = to_product_card(
            item,
            trip_date=outfit.date,
            category=category,
            item_label=item_label,
            item_text=item_text,
            max_price=budget,
            size_hint=size_hint,
        )
        if card is None:
            continue
        products.append(card)
        if len(products) >= n:
            break
    return products
