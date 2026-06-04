"""Build Taobao search plans from outfit items and user preferences."""

from __future__ import annotations

from datetime import date
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.utils.enrichment import parse_outfit_items
from src.graph.state import DailyOutfit, TripPreferences
from src.services.budget import budget_for_category, infer_item_category
from src.services.llm import get_chat_model, invoke_structured, load_prompt
from src.services.sizing import infer_size_hint

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
    parts: list[str] = []
    if prefs.gender and prefs.gender not in {"不限", ""}:
        parts.append(prefs.gender)
    style = (prefs.style or "休闲").split("、")[0]
    if style:
        parts.append(style)
    parts.append(item_text.strip())
    size = infer_size_hint(prefs.height_cm, prefs.weight_kg, prefs.gender)
    if size:
        parts.append(size)
    return " ".join(parts)[:80]


def _fallback_plans(outfit: DailyOutfit, prefs: TripPreferences) -> list[ShoppingSearchItem]:
    parsed = parse_outfit_items(outfit.outfit_summary)
    plans: list[ShoppingSearchItem] = []
    for label, text in parsed:
        category = _label_category(label)
        max_price = budget_for_category(category, prefs) or prefs.budget_per_item or 9999.0
        plans.append(
            ShoppingSearchItem(
                date=outfit.date,
                label=label,
                item_text=text,
                keyword=_fallback_keyword(label, text, prefs),
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
    llm=None,
    use_llm: bool = True,
) -> list[ShoppingSearchItem]:
    """
    Produce one search plan per outfit item, using LLM when available.

    Falls back to rule-based keywords on LLM failure.
    """
    if not outfits:
        return []

    fallback_all: list[ShoppingSearchItem] = []
    for outfit in outfits:
        fallback_all.extend(_fallback_plans(outfit, prefs))

    if not use_llm:
        return fallback_all

    size_hint = infer_size_hint(prefs.height_cm, prefs.weight_kg, prefs.gender)
    outfit_lines = []
    for outfit in outfits:
        items = parse_outfit_items(outfit.outfit_summary)
        item_str = "；".join(f"{label}:{text}" for label, text in items)
        outfit_lines.append(f"- {outfit.date}: {item_str}")

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
        )
        if result.items:
            cleaned: list[ShoppingSearchItem] = []
            for item in result.items:
                cat = item.category if item.category in {"top", "bottom", "shoes", "acc"} else _label_category(item.label)
                max_p = item.max_price if item.max_price > 0 else (budget_for_category(cat, prefs) or 9999.0)
                cleaned.append(
                    item.model_copy(
                        update={
                            "category": cat,
                            "max_price": max_p,
                            "size_hint": item.size_hint or size_hint,
                        }
                    )
                )
            return cleaned
    except Exception:
        pass

    return fallback_all
