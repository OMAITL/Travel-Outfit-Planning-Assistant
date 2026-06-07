"""Build Taobao search plans from outfit items and user preferences."""

from __future__ import annotations

from datetime import date
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.utils.enrichment import expand_outfit_item_slots, is_purchasable_item_text, parse_outfit_items
from src.graph.state import DailyOutfit, DayOutfitTrend, TripPreferences
from src.services.budget import budget_for_category, infer_item_category
from src.services.llm import get_chat_model, invoke_structured, load_prompt
from src.services.sizing import infer_size_hint
from src.services.taobao_keyword import build_item_search_keyword, simplify_item_for_search

Category = Literal["top", "bottom", "shoes", "acc"]
LABEL_TO_CATEGORY: dict[str, Category] = {
    "上装": "top",
    "内搭": "top",
    "外套": "top",
    "下装": "bottom",
    "鞋": "shoes",
    "配饰": "acc",
    "包": "acc",
}


class ShoppingSearchItem(BaseModel):
    date: date
    label: str
    item_text: str
    keyword: str
    category: Category
    max_price: float
    size_hint: str = ""


class ShoppingSearchBatch(BaseModel):
    items: list[ShoppingSearchItem] = Field(default_factory=list)


def _label_category(label: str) -> Category:
    return LABEL_TO_CATEGORY.get(label, infer_item_category(label))  # type: ignore[return-value]


def _fallback_keyword(label: str, item_text: str, prefs: TripPreferences) -> str:
    """Short Taobao query — keep color and core garment type."""
    return build_item_search_keyword(
        item_text.strip(),
        gender=prefs.gender,
        style=prefs.style,
    )


def _category_fallback_keyword(category: Category, prefs: TripPreferences) -> str:
    gender = prefs.gender if prefs.gender and prefs.gender not in {"不限", ""} else "女"
    style = (prefs.style or "休闲").split("、")[0]
    defaults = {
        "top": "上衣",
        "bottom": "裤子",
        "shoes": "鞋",
        "acc": "配饰",
    }
    return f"{gender} {style} {defaults.get(category, '穿搭')}"[:40]


def _dedupe_search_plans(plans: list[ShoppingSearchItem]) -> list[ShoppingSearchItem]:
    """One API call per (date, label, item_text); keep first occurrence."""
    seen: set[tuple[date, str, str]] = set()
    unique: list[ShoppingSearchItem] = []
    for plan in plans:
        key = (plan.date, plan.label, plan.item_text)
        if key in seen:
            continue
        seen.add(key)
        unique.append(plan)
    return unique


def _merge_llm_plans(
    expected: list[ShoppingSearchItem],
    llm_items: list[ShoppingSearchItem],
    prefs: TripPreferences,
    *,
    size_hint: str,
) -> list[ShoppingSearchItem]:
    """Align LLM keywords to outfit slots — never add extra search rows."""
    llm_map = {(item.date, item.label, item.item_text): item for item in llm_items}
    llm_by_label = {(item.date, item.label): item for item in llm_items}
    merged: list[ShoppingSearchItem] = []
    for plan in expected:
        llm_item = llm_map.get((plan.date, plan.label, plan.item_text))
        if llm_item is None:
            llm_item = llm_by_label.get((plan.date, plan.label))
        if llm_item is None:
            merged.append(plan)
            continue
        cat = plan.category
        cat_budget = budget_for_category(cat, prefs)
        max_p = cat_budget if cat_budget and cat_budget > 0 else plan.max_price
        search_text = simplify_item_for_search(llm_item.item_text or plan.item_text)
        merged.append(
            plan.model_copy(
                update={
                    "item_text": llm_item.item_text or plan.item_text,
                    "keyword": (llm_item.keyword or "").strip()
                    or _fallback_keyword(plan.label, search_text, prefs),
                    "max_price": max_p,
                    "size_hint": llm_item.size_hint or size_hint or "",
                }
            )
        )
    return merged


def _fallback_plans(outfit: DailyOutfit, prefs: TripPreferences) -> list[ShoppingSearchItem]:
    parsed = expand_outfit_item_slots(parse_outfit_items(outfit.outfit_summary))
    stylist_keywords = [kw.strip() for kw in (outfit.search_keywords or []) if kw.strip()]
    plans: list[ShoppingSearchItem] = []
    slot_index = 0
    for label, text in parsed:
        if _is_skippable_item_text(text):
            continue
        category = _label_category(label)
        max_price = budget_for_category(category, prefs) or prefs.budget_per_item or 9999.0
        keyword = _fallback_keyword(label, text, prefs)
        if slot_index < len(stylist_keywords):
            keyword = stylist_keywords[slot_index]
        slot_index += 1
        plans.append(
            ShoppingSearchItem(
                date=outfit.date,
                label=label,
                item_text=text,
                keyword=keyword,
                category=category,
                max_price=max_price,
                size_hint=infer_size_hint(prefs.height_cm, prefs.weight_kg, prefs.gender),
            )
        )
    return plans


def _is_skippable_item_text(text: str) -> bool:
    cleaned = text.strip().lower()
    if cleaned in {"", "无", "不需要", "none", "n/a", "-", "—"}:
        return True
    return not is_purchasable_item_text(text)


def _trend_item_for_category(trend: DayOutfitTrend | None, category: Category) -> str:
    if trend is None:
        return ""
    mapping = {
        "top": trend.top_picks,
        "bottom": trend.bottom_picks,
        "shoes": trend.shoes_picks,
        "acc": [*trend.bag_picks, *trend.acc_picks],
    }
    picks = mapping.get(category, [])
    return picks[0] if picks else ""


def _trend_plans(
    outfit: DailyOutfit,
    prefs: TripPreferences,
    trend: DayOutfitTrend | None,
) -> list[ShoppingSearchItem]:
    parsed = expand_outfit_item_slots(parse_outfit_items(outfit.outfit_summary))
    stylist_keywords = [kw.strip() for kw in (outfit.search_keywords or []) if kw.strip()]
    plans: list[ShoppingSearchItem] = []
    slot_index = 0
    for label, text in parsed:
        if _is_skippable_item_text(text):
            continue
        category = _label_category(label)
        trend_text = _trend_item_for_category(trend, category)
        item_text = text or trend_text
        search_text = simplify_item_for_search(trend_text or text)
        max_price = budget_for_category(category, prefs) or prefs.budget_per_item or 9999.0
        keyword = _fallback_keyword(label, search_text, prefs)
        if slot_index < len(stylist_keywords):
            keyword = stylist_keywords[slot_index]
        slot_index += 1
        plans.append(
            ShoppingSearchItem(
                date=outfit.date,
                label=label,
                item_text=item_text,
                keyword=keyword,
                category=category,
                max_price=max_price,
                size_hint=infer_size_hint(prefs.height_cm, prefs.weight_kg, prefs.gender),
            )
        )
    return plans


def enrich_search_plans(
    outfits: list[DailyOutfit],
    prefs: TripPreferences,
    *,
    trends: list[DayOutfitTrend] | None = None,
    llm=None,
    use_llm: bool = True,
) -> list[ShoppingSearchItem]:
    """
    Produce one search plan per outfit item, using LLM when available.

    Falls back to rule-based keywords on LLM failure.
    """
    if not outfits:
        return []

    trend_map = {row.date: row for row in (trends or [])}
    fallback_all: list[ShoppingSearchItem] = []
    for outfit in outfits:
        fallback_all.extend(_trend_plans(outfit, prefs, trend_map.get(outfit.date)))

    if not use_llm:
        return fallback_all

    size_hint = infer_size_hint(prefs.height_cm, prefs.weight_kg, prefs.gender)
    outfit_lines = []
    for outfit in outfits:
        items = parse_outfit_items(outfit.outfit_summary)
        item_str = "；".join(f"{label}:{text}" for label, text in items)
        trend = trend_map.get(outfit.date)
        trend_hint = ""
        if trend:
            trend_hint = (
                f" | XHS趋势: 上装={','.join(trend.top_picks[:2]) or '-'}, "
                f"下装={','.join(trend.bottom_picks[:2]) or '-'}, "
                f"鞋={','.join(trend.shoes_picks[:2]) or '-'}"
            )
        outfit_lines.append(f"- {outfit.date}: {item_str}{trend_hint}")

    bbc = prefs.budget_by_category.model_dump() if prefs.budget_by_category else {}
    user_msg = (
        f"用户：性别={prefs.gender or '女'}，风格={prefs.style}，"
        f"身高={prefs.height_cm}cm，体重={prefs.weight_kg}kg，"
        f"体型={prefs.body_type or '标准'}，肤色={prefs.skin_tone or '自然'}，"
        f"避雷={','.join(prefs.avoid_items) or '无'}。\n"
        f"分类预算(元)：{bbc or '未设置'}\n"
        f"尺码参考：{size_hint or '未知'}\n\n"
        "每日穿搭单品：\n"
        + "\n".join(outfit_lines)
        + "\n\n为每个单品生成一条淘宝搜索词 keyword（含风格、尺码线索），"
        "优先使用小红书趋势中的具体单品名（如德训鞋、灰色短款针织）。"
        "并指定 category(top/bottom/shoes/acc) 与 max_price(元)。"
    )

    try:
        model = llm or get_chat_model()
        result: ShoppingSearchBatch = invoke_structured(
            model,
            ShoppingSearchBatch,
            [
                SystemMessage(content=load_prompt("shopping.md")),
                HumanMessage(content=user_msg),
            ],
            retries=1,
            operation="shopping_keywords",
        )
        if result.items:
            return _dedupe_search_plans(
                _merge_llm_plans(fallback_all, result.items, prefs, size_hint=size_hint)
            )
    except Exception:
        pass

    return _dedupe_search_plans(fallback_all)
