"""Shopping Agent node — LLM-enriched keywords + budget-aware OneBound search."""

from __future__ import annotations

from typing import Any

from src.config import get_settings
from src.graph.state import PlanningState, ProductCard
from src.services.product_matcher import pick_top_n
from src.services.search_enrichment import ShoppingSearchItem, enrich_search_plans
from src.tools.product_search import ProductSearchError, search_products

MAX_PER_ITEM = 3


def _search_keyword(
    keyword: str,
    budget: float | None,
) -> tuple[list[dict[str, Any]], ProductSearchError | None]:
    try:
        items = search_products(keyword, max_price=budget)
        if not items and budget is not None and budget > 0:
            items = search_products(keyword, max_price=None)
        return items, None
    except ProductSearchError as exc:
        return [], exc
    except Exception as exc:
        return [], ProductSearchError(f"商品搜索失败: {exc}", source="unknown")


def _outfit_for_date(state: PlanningState, day):
    for outfit in state.outfits:
        if outfit.date == day:
            return outfit
    return None


def shopping_node(state: PlanningState, *, llm=None) -> PlanningState:
    if not state.outfits:
        return state.append_trace("Shopping", "skipped: no outfits", level="warning")

    settings = get_settings()
    prefs = state.trip.preferences if state.trip else None
    if prefs is None:
        return state.append_trace("Shopping", "skipped: no preferences", level="warning")

    all_products: list[ProductCard] = []
    calls_used = 0
    max_calls = (
        settings.justoneapi_max_calls_per_run
        if settings.product_source == "justoneapi"
        else settings.onebound_max_calls_per_run
    )
    quota_exceeded = False

    search_plans = enrich_search_plans(state.outfits, prefs, llm=llm)
    state = state.append_trace(
        "Shopping",
        f"searching {len(search_plans)} item(s), max {MAX_PER_ITEM}/item, {max_calls} API calls",
    )

    for plan in search_plans:
        if quota_exceeded or calls_used >= max_calls:
            break

        outfit = _outfit_for_date(state, plan.date)
        if outfit is None:
            continue

        budget = plan.max_price if plan.max_price > 0 else None
        items, api_error = _search_keyword(plan.keyword, budget)
        calls_used += 1

        if api_error is not None:
            err_text = str(api_error)
            if "4013" in err_text or "超限" in err_text:
                quota_exceeded = True
            state = (
                state.append_error(err_text)
                .append_trace("Shopping", f"search failed: {plan.keyword}", level="warning")
            )
            continue

        picked = pick_top_n(
            items,
            outfit,
            n=MAX_PER_ITEM,
            budget=budget,
            category=plan.category,
            item_label=plan.label,
            item_text=plan.item_text,
            size_hint=plan.size_hint,
            strict_budget=True,
        )
        all_products.extend(picked)

        if not picked:
            state = state.append_trace(
                "Shopping",
                f"no in-budget products for {plan.label} ({plan.keyword})",
                level="warning",
            )

    state = state.append_trace(
        "Shopping",
        f"selected {len(all_products)} product(s) using {calls_used} API call(s)",
    )
    return state.model_copy(update={"products": all_products})
