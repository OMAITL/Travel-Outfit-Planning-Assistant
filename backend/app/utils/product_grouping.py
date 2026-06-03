"""Assign ProductCard list to parsed outfit items for per-item product tabs."""

from __future__ import annotations

import re

from src.graph.state import DailyOutfit, ProductCard


def _item_match_tokens(text: str) -> set[str]:
    """Extract meaningful tokens from outfit item text for title matching."""
    cleaned = re.sub(r"^(上装|下装|鞋|外套|配饰|内搭|包)[：:]\s*", "", text).strip()
    tokens: set[str] = set()
    if len(cleaned) >= 2:
        tokens.add(cleaned)
    for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", cleaned):
        tokens.add(chunk)
    for chunk in re.split(r"\s+", cleaned):
        chunk = chunk.strip()
        if len(chunk) >= 2:
            tokens.add(chunk)
    return tokens


def _score_product_for_item(product: ProductCard, item_text: str) -> float:
    title = product.title.lower()
    score = 0.0
    for token in _item_match_tokens(item_text):
        if token.lower() in title or token in product.title:
            score += len(token)
    return score


def assign_products_to_items(
    outfit: DailyOutfit | None,
    products: list[ProductCard],
    *,
    max_per_item: int = 5,
) -> list[tuple[str, str, list[ProductCard]]]:
    """
    Group day-level products under each outfit item.

    Returns list of (label, item_text, products[:max_per_item]).
    Unassigned products are distributed round-robin; empty items get [].
    """
    from app.utils.enrichment import parse_outfit_items

    if outfit is None:
        return [("穿搭", "全套方案", products[:max_per_item])]

    items = parse_outfit_items(outfit.outfit_summary)
    keywords = outfit.search_keywords or []
    assigned: list[tuple[str, str, list[ProductCard]]] = []
    used_ids: set[str] = set()

    for index, (label, text) in enumerate(items):
        matched: list[ProductCard] = []
        ranked = sorted(
            products,
            key=lambda p: _score_product_for_item(p, text),
            reverse=True,
        )
        for product in ranked:
            pid = product.num_iid or product.detail_url
            if pid in used_ids:
                continue
            if _score_product_for_item(product, text) > 0:
                matched.append(product)
                used_ids.add(pid)
            if len(matched) >= max_per_item:
                break

        if not matched and index < len(keywords):
            kw = keywords[index]
            for product in products:
                pid = product.num_iid or product.detail_url
                if pid in used_ids:
                    continue
                if kw[:4] in product.title or kw in product.title:
                    matched.append(product)
                    used_ids.add(pid)
                if len(matched) >= max_per_item:
                    break

        assigned.append((label, text, matched))

    remaining = [p for p in products if (p.num_iid or p.detail_url) not in used_ids]
    for index, product in enumerate(remaining):
        bucket = index % len(assigned) if assigned else 0
        if assigned and len(assigned[bucket][2]) < max_per_item:
            label, text, group = assigned[bucket]
            group = [*group, product]
            assigned[bucket] = (label, text, group)

    return assigned
