"""Product matching and ranking for Shopping Agent."""

from __future__ import annotations

import re
from typing import Any

from src.graph.state import DailyOutfit, ProductCard
from src.services.budget import category_compatible, infer_item_category
from src.services.taobao_keyword import (
    _COLOR_ALIASES,
    _COLOR_CONFLICTS,
    extract_item_colors,
)


def _tokenize(text: str) -> set[str]:
    tokens: set[str] = set()
    for chunk in re.split(r"\s+", text.strip()):
        if not chunk:
            continue
        tokens.add(chunk.lower())
        if re.search(r"[\u4e00-\u9fff]", chunk):
            tokens.update(char for char in chunk if "\u4e00" <= char <= "\u9fff")
    return tokens


def _item_match_tokens(text: str) -> set[str]:
    cleaned = re.sub(r"^(上装|下装|鞋|外套|配饰|内搭|包)[：:]\s*", "", text).strip()
    tokens: set[str] = set()
    if len(cleaned) >= 2:
        tokens.add(cleaned)
    for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", cleaned):
        tokens.add(chunk)
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


def _title_has_color(title: str, color_key: str) -> bool:
    aliases = _COLOR_ALIASES.get(color_key, (color_key,))
    return any(alias in title for alias in aliases)


def color_match_score(title: str, item_text: str | None) -> float:
    """Reward matching colors and penalize clearly conflicting colors in titles."""
    if not item_text:
        return 0.0
    expected = extract_item_colors(item_text)
    if not expected:
        return 0.0

    score = 0.0
    for color_key in expected:
        if _title_has_color(title, color_key):
            score += 40.0
        else:
            for conflict in _COLOR_CONFLICTS.get(color_key, ()):
                if conflict in title and not any(
                    _title_has_color(title, expected_key) for expected_key in expected
                ):
                    score -= 60.0
                    break
    return score


def popularity_score(item: dict[str, Any]) -> float:
    """Prefer higher sales / comments / seller rating from Taobao search payload."""
    score = 0.0

    sales = item.get("sales")
    if isinstance(sales, (int, float)) and sales > 0:
        score += min(float(sales) / 500.0, 12.0)

    order_uv = item.get("order_pay_uv")
    if isinstance(order_uv, (int, float)) and order_uv > 0:
        score += min(float(order_uv) / 200.0, 10.0)

    comments = item.get("comment_count")
    if isinstance(comments, (int, float)) and comments > 0:
        score += min(float(comments) / 1000.0, 8.0)

    seller_rating = item.get("seller_good_rating")
    if isinstance(seller_rating, (int, float)) and seller_rating > 0:
        score += min(float(seller_rating) / 2000.0, 4.0)

    return score


def score_product_for_item(
    item: dict[str, Any],
    *,
    item_text: str | None = None,
    outfit: DailyOutfit | None = None,
    budget: float | None = None,
) -> float:
    """Score a Taobao item against a specific outfit slot."""
    title = str(item.get("title") or "")
    title_lower = title.lower()
    score = popularity_score(item)

    if item_text:
        score += color_match_score(title, item_text)
        for token in _item_match_tokens(item_text):
            if token.lower() in title_lower or token in title:
                score += len(token) * 4.0
        if item_text.strip() and item_text.strip() in title:
            score += 80.0

    if outfit is not None:
        title_tokens = _tokenize(title)
        keyword_tokens: set[str] = set()
        for keyword in outfit.search_keywords:
            keyword_tokens |= _tokenize(keyword)
        keyword_tokens |= _tokenize(outfit.outfit_summary)
        overlap = len(title_tokens & keyword_tokens)
        score += overlap * 2.0 + _keyword_hits(title_lower, outfit) * 2.0

    price = _parse_price(item.get("promotion_price") or item.get("price"))
    if budget is not None and budget > 0:
        if price <= budget:
            score += 5.0
        elif price <= budget * 1.05:
            score += 1.0
        else:
            score -= 50.0

    return score


def score_product(
    item: dict[str, Any],
    outfit: DailyOutfit,
    budget: float | None = None,
) -> float:
    """Score a Taobao item against a daily outfit plan."""
    return score_product_for_item(item, outfit=outfit, budget=budget)


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


_ADULT_EXCLUDE_TOKENS = ("儿童", "童装", "童款", "宝宝", "婴儿", "幼儿", "中大童", "小童")


def _is_adult_product(title: str) -> bool:
    return not any(token in title for token in _ADULT_EXCLUDE_TOKENS)


def _rank_candidates(
    candidates: list[dict[str, Any]],
    *,
    outfit: DailyOutfit,
    budget: float | None,
    category: str | None,
    item_text: str | None,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for item in dedupe_by_iid(candidates):
        title = str(item.get("title") or "")
        if not _is_adult_product(title):
            continue
        if category and not category_compatible(category, title, item_text=item_text or ""):
            continue
        filtered.append(item)

    return sorted(
        filtered,
        key=lambda item: score_product_for_item(
            item,
            item_text=item_text,
            outfit=outfit,
            budget=budget,
        ),
        reverse=True,
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
    """Deduplicate, score, and return up to N product cards; backfill to N when possible."""
    ranked = _rank_candidates(
        candidates,
        outfit=outfit,
        budget=budget,
        category=category,
        item_text=item_text,
    )

    def _collect(
        rows: list[dict[str, Any]],
        *,
        budget_cap: float | None,
        min_color_score: float | None = None,
    ) -> list[ProductCard]:
        products: list[ProductCard] = []
        seen_ids: set[str] = set()
        for item in rows:
            iid = str(item.get("num_iid") or item.get("detail_url") or "")
            if iid and iid in seen_ids:
                continue
            price = _parse_price(item.get("promotion_price") or item.get("price"))
            if budget_cap is not None and budget_cap > 0 and price > budget_cap:
                continue
            if min_color_score is not None and item_text:
                if color_match_score(str(item.get("title") or ""), item_text) < min_color_score:
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
            if iid:
                seen_ids.add(iid)
            products.append(card)
            if len(products) >= n:
                break
        return products

    has_color = bool(item_text and extract_item_colors(item_text))
    if has_color:
        products = _collect(ranked, budget_cap=budget if strict_budget else None, min_color_score=20.0)
        if len(products) >= n:
            return products[:n]
        if strict_budget and budget is not None and budget > 0:
            products = _collect(ranked, budget_cap=budget * 1.15, min_color_score=20.0)
            if products:
                return products[:n]
        return products[:n]

    products = _collect(ranked, budget_cap=budget if strict_budget else None)
    if len(products) >= n:
        return products[:n]

    if strict_budget and budget is not None and budget > 0:
        products = _collect(ranked, budget_cap=budget * 1.15)
        if len(products) >= n:
            return products[:n]

    extra = _collect(ranked, budget_cap=None)
    merged: list[ProductCard] = []
    seen: set[str] = set()
    for card in [*products, *extra]:
        key = card.num_iid or card.detail_url
        if key in seen:
            continue
        seen.add(key)
        merged.append(card)
        if len(merged) >= n:
            break
    return merged
