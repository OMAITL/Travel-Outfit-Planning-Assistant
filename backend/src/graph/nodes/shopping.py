"""Shopping Agent node — search OneBound and pick top products per day."""

from __future__ import annotations

from typing import Any

from src.config import get_settings
from src.graph.state import PlanningState, ProductCard
from src.services.product_matcher import pick_top_n
from src.tools.onebound import OneBoundError, search_taobao_items


def _search_keyword(
    keyword: str,
    budget: float | None,
) -> tuple[list[dict[str, Any]], OneBoundError | None]:
    """Search with budget filter; retry without price cap if the first pass is empty."""
    try:
        items = search_taobao_items(keyword, max_price=budget)
        if not items and budget is not None and budget > 0:
            items = search_taobao_items(keyword, max_price=None)
        return items, None
    except OneBoundError as exc:
        return [], exc


def shopping_node(state: PlanningState) -> PlanningState:
    if not state.outfits:
        return state.append_trace("Shopping", "skipped: no outfits", level="warning")

    settings = get_settings()
    budget = state.trip.preferences.budget_per_item if state.trip else None
    all_products: list[ProductCard] = []
    calls_used = 0
    max_calls = settings.onebound_max_calls_per_run
    quota_exceeded = False

    state = state.append_trace("Shopping", f"matching products (max {max_calls} API calls)")

    for outfit in state.outfits:
        if quota_exceeded:
            break

        candidates: list[dict[str, Any]] = []
        keywords = outfit.search_keywords[:2] or [outfit.outfit_summary[:30]]

        for keyword in keywords:
            if calls_used >= max_calls:
                state = state.append_trace(
                    "Shopping",
                    f"call limit reached ({max_calls}); skipping remaining searches",
                    level="warning",
                )
                break

            items, api_error = _search_keyword(keyword, budget)
            if api_error is not None:
                if api_error.error_code == "4013":
                    quota_exceeded = True
                state = (
                    state.append_error(str(api_error))
                    .append_trace("Shopping", f"search failed: {keyword}", level="warning")
                )
                break

            candidates.extend(items)
            calls_used += 1

        day_products = pick_top_n(candidates, outfit, n=5, budget=budget)
        all_products.extend(day_products)

        if not day_products:
            state = state.append_trace(
                "Shopping",
                f"no products matched for {outfit.date}",
                level="warning",
            )

    state = state.append_trace(
        "Shopping",
        f"selected {len(all_products)} product(s) using {calls_used} API call(s)",
    )
    return state.model_copy(update={"products": all_products})
