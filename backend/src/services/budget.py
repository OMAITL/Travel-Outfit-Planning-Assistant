"""Budget helpers — category inference and per-item limits."""

from __future__ import annotations

from src.graph.state import BudgetByCategory, TripPreferences

_CATEGORY_HINTS: dict[str, tuple[str, ...]] = {
    "shoes": ("鞋", "靴", "凉鞋", "拖鞋", "帆布鞋", "运动鞋", "boot", "sneaker"),
    "bottom": ("裤", "裙", "短裤", "半裙", "阔腿裤", "牛仔裤", "skirt"),
    "acc": ("帽", "包", "围巾", "腰带", "配饰", "眼镜", "首饰", "手表", "袜", "手套"),
}


def infer_item_category(keyword: str) -> str:
    text = keyword.lower()
    for category, hints in _CATEGORY_HINTS.items():
        if any(hint in text for hint in hints):
            return category
    return "top"


def category_compatible(expected: str, title: str, *, item_text: str = "") -> bool:
    """Return True when a Taobao title plausibly matches the expected outfit slot.

    The category is inferred from the **title alone** — mixing in ``item_text`` used to
    let any product (e.g. a 草帽) count as a 下装 whenever the item described a 裙, which
    broke the strict item↔product mapping. ``item_text`` is only consulted for the narrow
    dress/连体 cases where the garment legitimately spans top+bottom.
    """
    inferred = infer_item_category(title)
    if inferred == expected:
        return True
    # A dress / jumpsuit covers both top and bottom slots.
    if expected in {"top", "bottom"} and any(
        token in title for token in ("连衣裙", "连身裙", "连体裤", "连衣裤")
    ):
        return True
    # Outfit explicitly calls for a skirt and the product is a skirt (not footwear).
    if expected == "bottom" and "裙" in item_text and "裙" in title and "鞋" not in title:
        return True
    return False


def budget_for_category(category: str, prefs: TripPreferences) -> float | None:
    bbc = prefs.budget_by_category
    if bbc is not None:
        value = getattr(bbc, category, 0.0)
        if value and value > 0:
            return value
    return prefs.budget_per_item


def budget_for_keyword(keyword: str, prefs: TripPreferences) -> float | None:
    return budget_for_category(infer_item_category(keyword), prefs)


def normalize_budget_fields(
    *,
    budget_by_category: BudgetByCategory | dict[str, float] | None = None,
    budget_per_item: float | None = None,
    budget_total: float | None = None,
) -> tuple[float | None, float | None, BudgetByCategory | None]:
    """Derive legacy budget fields from category budgets when needed."""
    if not budget_by_category:
        return budget_per_item, budget_total, None

    bbc = (
        budget_by_category
        if isinstance(budget_by_category, BudgetByCategory)
        else BudgetByCategory.model_validate(budget_by_category)
    )
    per_item = budget_per_item if budget_per_item and budget_per_item > 0 else bbc.max_item
    total = budget_total if budget_total and budget_total > 0 else bbc.total
    if per_item <= 0:
        per_item = None
    if total <= 0:
        total = None
    return per_item, total, bbc
