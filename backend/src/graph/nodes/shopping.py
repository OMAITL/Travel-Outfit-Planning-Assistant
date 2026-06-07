"""Shopping Agent node — budget-aware Taobao search with deduped API calls."""

from __future__ import annotations

import logging
from typing import Any

from src.config import get_settings
from src.graph.state import PlanningState, ProductCard, TripPreferences
from src.services.product_matcher import pick_top_n
from src.services.search_enrichment import ShoppingSearchItem, enrich_search_plans
from src.services.taobao_keyword import build_item_search_keyword, simplify_item_for_search
from src.tools.product_search import ProductSearchError, search_products

MAX_PER_ITEM = 3
logger = logging.getLogger(__name__)


def _search_keyword(
    keyword: str,
) -> tuple[list[dict[str, Any]], ProductSearchError | None]:
    """
    Search Taobao without API-side price filter.

    Just One / OneBound endPrice often returns empty for specific keywords;
    budget is enforced when picking products client-side.
    """
    try:
        items = search_products(keyword, max_price=None)
        return items, None
    except ProductSearchError as exc:
        return [], exc
    except Exception as exc:
        return [], ProductSearchError(f"商品搜索失败: {exc}", source="unknown")


def _keyword_variants(plan: ShoppingSearchItem, prefs: TripPreferences) -> list[str]:
    full = build_item_search_keyword(
        plan.item_text,
        gender=prefs.gender,
        style=prefs.style,
    )
    core = simplify_item_for_search(plan.item_text)
    variants = [plan.keyword.strip(), full]
    if core and core not in variants:
        variants.append(
            build_item_search_keyword(core, gender=prefs.gender, style=prefs.style)
        )
    short = " ".join(
        part
        for part in [
            prefs.gender if prefs.gender not in {None, "", "不限"} else "女",
            (prefs.style or "休闲").split("、")[0],
            core,
        ]
        if part
    )[:50]
    if short and short not in variants:
        variants.append(short)
    return variants


def _search_and_pick(
    plan: ShoppingSearchItem,
    outfit,
    prefs: TripPreferences,
    *,
    keyword_cache: dict[str, list[dict[str, Any]]],
    max_retries: int = 3,
) -> tuple[list[ProductCard], str, int]:
    """Return (products, keyword_used, api_calls_used). Accumulates until MAX_PER_ITEM hits."""
    budget = plan.max_price if plan.max_price > 0 else None
    variants = _keyword_variants(plan, prefs)[:max_retries]
    calls = 0
    collected: list[ProductCard] = []
    seen_ids: set[str] = set()
    keyword_used = variants[0] if variants else plan.keyword.strip()

    for keyword in variants:
        if len(collected) >= MAX_PER_ITEM:
            break
        cache_key = keyword.lower()
        if cache_key in keyword_cache:
            items = keyword_cache[cache_key]
        else:
            items, api_error = _search_keyword(keyword)
            calls += 1
            if api_error is not None:
                if collected:
                    break
                return [], keyword, calls
            keyword_cache[cache_key] = items
            logger.info(
                "Taobao API keyword=%r items=%d date=%s label=%s budget=%s",
                keyword,
                len(items),
                plan.date,
                plan.label,
                budget,
            )

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
        if picked:
            keyword_used = keyword
        for card in picked:
            key = card.num_iid or card.detail_url
            if key in seen_ids:
                continue
            seen_ids.add(key)
            collected.append(card)
            if len(collected) >= MAX_PER_ITEM:
                break

    if len(collected) < MAX_PER_ITEM and variants:
        # Last resort: relax budget slightly on the best keyword tried.
        cache_key = keyword_used.lower()
        items = keyword_cache.get(cache_key, [])
        if items:
            relaxed = pick_top_n(
                items,
                outfit,
                n=MAX_PER_ITEM,
                budget=budget,
                category=plan.category,
                item_label=plan.label,
                item_text=plan.item_text,
                size_hint=plan.size_hint,
                strict_budget=False,
            )
            for card in relaxed:
                key = card.num_iid or card.detail_url
                if key in seen_ids:
                    continue
                seen_ids.add(key)
                collected.append(card)
                if len(collected) >= MAX_PER_ITEM:
                    break

    return collected[:MAX_PER_ITEM], keyword_used, calls


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

    search_plans = enrich_search_plans(
        state.outfits,
        prefs,
        trends=state.outfit_trends,
        llm=llm,
    )
    state = state.append_trace(
        "Shopping",
        f"searching {len(search_plans)} item slot(s), max {max_calls} API calls",
    )

    keyword_cache: dict[str, list[dict[str, Any]]] = {}

    for plan_index, plan in enumerate(search_plans):
        if quota_exceeded or calls_used >= max_calls:
            logger.warning(
                "Taobao API quota reached after %d/%d calls — remaining %d item slot(s) skipped",
                calls_used,
                max_calls,
                len(search_plans) - plan_index,
            )
            state = state.append_trace(
                "Shopping",
                f"quota reached, skipped remaining items after {calls_used} call(s)",
                level="warning",
            )
            quota_exceeded = True
            break

        outfit = _outfit_for_date(state, plan.date)
        if outfit is None:
            continue

        budget = plan.max_price if plan.max_price > 0 else None
        picked, keyword_used, used = _search_and_pick(
            plan,
            outfit,
            prefs,
            keyword_cache=keyword_cache,
        )
        calls_used += used
        all_products.extend(picked)

        budget_note = f"¥{budget:.0f}" if budget else "no cap"
        if picked:
            prices = ", ".join(f"¥{p.price:.0f}" for p in picked[:2])
            state = state.append_trace(
                "Shopping",
                f"{plan.date} {plan.label} ≤{budget_note}: {len(picked)} via「{keyword_used}」({prices})",
            )
        else:
            state = state.append_trace(
                "Shopping",
                f"{plan.date} {plan.label} ≤{budget_note}: 0 hits for「{keyword_used}」",
                level="warning",
            )

    state = state.append_trace(
        "Shopping",
        f"selected {len(all_products)} product(s), {calls_used} Taobao API call(s)",
    )
    return state.model_copy(update={"products": all_products})
