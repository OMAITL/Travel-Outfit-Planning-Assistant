"""Assign ProductCard list to parsed outfit items for per-item product tabs."""

from __future__ import annotations

import re

from src.graph.state import DailyOutfit, ProductCard
from src.services.budget import category_compatible, infer_item_category
from src.services.product_matcher import color_match_score


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
    tagged = (product.item_text or "").strip()
    if tagged:
        if tagged == item_text:
            return 1000.0
        if item_text in tagged or tagged in item_text:
            return 500.0
    title = product.title.lower()
    score = color_match_score(product.title, item_text)
    for token in _item_match_tokens(item_text):
        if token.lower() in title or token in product.title:
            score += len(token)
    return score


def _label_category(label: str) -> str:
    mapping = {
        "上装": "top",
        "内搭": "top",
        "外套": "top",
        "下装": "bottom",
        "鞋": "shoes",
        "配饰": "acc",
        "包": "acc",
    }
    return mapping.get(label, infer_item_category(label))


def _item_text_matches(product: ProductCard, item_text: str) -> bool:
    tagged = (product.item_text or "").strip()
    target = item_text.strip()
    if not tagged:
        return False
    if tagged == target:
        return True
    return tagged in target or target in tagged


def assign_products_to_items(
    outfit: DailyOutfit | None,
    products: list[ProductCard],
    *,
    max_per_item: int = 3,
) -> list[tuple[str, str, list[ProductCard]]]:
    """
    Group day-level products under each outfit item.

    Returns list of (label, item_text, products[:max_per_item]).
    Products are matched by shopping metadata first, then title overlap.
    """
    from app.utils.enrichment import expand_outfit_item_slots, is_purchasable_item_text, parse_outfit_items

    if outfit is None:
        return [("穿搭", "全套方案", products[:max_per_item])]

    items = expand_outfit_item_slots(parse_outfit_items(outfit.outfit_summary))
    items = [(label, text) for label, text in items if is_purchasable_item_text(text)]
    assigned: list[tuple[str, str, list[ProductCard]]] = []
    used_ids: set[str] = set()

    for label, text in items:
        category = _label_category(label)
        matched: list[ProductCard] = []

        # Stage 1 — products the Shopping Agent explicitly tagged for this exact item.
        tagged = [
            product
            for product in products
            if _item_text_matches(product, text)
            and category_compatible(category, product.title, item_text=text)
        ]
        tagged.sort(key=lambda p: _score_product_for_item(p, text), reverse=True)
        for product in tagged:
            pid = product.num_iid or product.detail_url
            if pid in used_ids:
                continue
            matched.append(product)
            used_ids.add(pid)
            if len(matched) >= max_per_item:
                break

        # Stage 2 — same category AND a genuine title/color match with this item.
        if len(matched) < max_per_item:
            ranked = sorted(
                products,
                key=lambda p: _score_product_for_item(p, text),
                reverse=True,
            )
            for product in ranked:
                pid = product.num_iid or product.detail_url
                if pid in used_ids:
                    continue
                if not category_compatible(category, product.title, item_text=text):
                    continue
                if _score_product_for_item(product, text) <= 0:
                    continue
                matched.append(product)
                used_ids.add(pid)
                if len(matched) >= max_per_item:
                    break

        assigned.append((label, text, matched[:max_per_item]))

    return assigned
