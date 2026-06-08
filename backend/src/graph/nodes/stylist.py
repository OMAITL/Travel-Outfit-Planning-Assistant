"""Stylist Agent node — LLM outfit planning from trip + weather."""

from __future__ import annotations

import json

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, model_validator

from src.graph.state import DailyOutfit, PlanningState
from src.services.body_profile import BodyProfile
from src.services.itinerary import day_all_spots
from src.services.llm import get_chat_model, invoke_structured, load_prompt


class StylistOutput(BaseModel):
    outfits: list[DailyOutfit] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_llm_payload(cls, value: object) -> object:
        """DeepSeek json_mode may return null, a bare array, or outfits: null."""
        if value is None:
            return {"outfits": []}
        if isinstance(value, list):
            return {"outfits": value}
        if isinstance(value, dict) and value.get("outfits") is None:
            return {**value, "outfits": []}
        return value


def _format_weather(state: PlanningState) -> str:
    if not state.weather:
        return "No forecast available; use destination season and typical climate."
    rows = []
    for day in state.weather:
        condition = day.condition.value if hasattr(day.condition, "value") else day.condition
        rows.append(
            f"- {day.date}: {condition}, {day.temp_min:.0f}~{day.temp_max:.0f}°C"
        )
    return "\n".join(rows)


def _format_itinerary(state: PlanningState) -> str:
    if not state.itinerary:
        return "No scenic spots assigned; plan outfits for general sightseeing."
    rows = []
    for row in state.itinerary:
        spots = day_all_spots(row)
        if row.morning or row.afternoon or row.evening:
            parts = []
            if row.morning:
                parts.append(f"上午 {row.morning}")
            if row.afternoon:
                parts.append(f"下午 {row.afternoon}")
            if row.evening:
                parts.append(f"晚间 {row.evening}")
            slot_line = f"- {row.date}: {' | '.join(parts)}"
            if len(spots) > 1:
                slot_line += (
                    f"（当日 {len(spots)} 个景点：{'、'.join(spots)}；"
                    "需一套穿搭同时适配以上全部景点）"
                )
            rows.append(slot_line)
            continue
        if len(spots) > 1:
            rows.append(
                f"- {row.date}: {'、'.join(spots)}"
                f"（当日多景点，需一套穿搭同时适配以上全部景点）"
            )
            continue
        spot_line = "、".join(spots) if spots else "（未指定景点，按城市通用游览）"
        rows.append(f"- {row.date}: {spot_line}")
    return "\n".join(rows)


def _format_trip(state: PlanningState) -> str:
    trip = state.trip
    if trip is None:
        return "Trip context unavailable."
    prefs = trip.preferences
    body = BodyProfile.from_preferences(prefs)
    payload = {
        "destination": trip.destination,
        "start_date": str(trip.start_date),
        "end_date": str(trip.end_date),
        "trip_days": trip.trip_days,
        "party_size": prefs.party_size,
        "activities": prefs.activities,
        "gender": prefs.gender,
        "style": prefs.style,
        "height_cm": prefs.height_cm,
        "weight_kg": prefs.weight_kg,
        "body_type": prefs.body_type,
        "skin_tone": prefs.skin_tone,
        "avoid_items": prefs.avoid_items,
        "spot_names": prefs.spot_names,
        "plan_mode": prefs.plan_mode,
        "budget_per_item": prefs.budget_per_item,
        "budget_total": prefs.budget_total,
        "budget_by_category": (
            prefs.budget_by_category.model_dump() if prefs.budget_by_category else None
        ),
    }
    constraints = body.stylist_constraints_zh()
    if constraints:
        payload["body_fit_notes"] = constraints
    return json.dumps(payload, ensure_ascii=False)


def _format_trends(state: PlanningState) -> str:
    if not state.outfit_trends:
        return "No Xiaohongshu trend data — plan from weather and user preferences only."
    rows = []
    for trend in sorted(state.outfit_trends, key=lambda item: item.date):
        rows.append(
            json.dumps(
                {
                    "date": str(trend.date),
                    "dominant_style": trend.dominant_style,
                    "top_picks": trend.top_picks,
                    "bottom_picks": trend.bottom_picks,
                    "shoes_picks": trend.shoes_picks,
                    "bag_picks": trend.bag_picks,
                    "acc_picks": trend.acc_picks,
                    "color_palette": trend.color_palette,
                    "scene_vibe": trend.scene_vibe,
                },
                ensure_ascii=False,
            )
        )
    return "\n".join(rows)


def _format_xhs_refs(state: PlanningState) -> str:
    if not state.outfit_inspirations:
        return "No XHS reference notes."
    by_date: dict = {}
    for ref in state.outfit_inspirations:
        by_date.setdefault(ref.trip_date, []).append(ref)
    rows = []
    for day in sorted(by_date):
        day_refs = sorted(by_date[day], key=lambda r: r.liked_count or 0, reverse=True)
        spot_hint = day_refs[0].search_keyword if day_refs else ""
        for ref in day_refs[:3]:
            rows.append(
                f"- {day} | spot keyword: {spot_hint} | {ref.liked_count or 0} likes | {ref.title}"
            )
    return "\n".join(rows)


def stylist_node(state: PlanningState, *, llm=None) -> PlanningState:
    if state.trip is None or not state.trip.is_complete:
        return state.append_trace("Stylist", "skipped: trip not ready", level="warning")

    state = state.append_trace("Stylist", "planning daily outfits")
    model = llm or get_chat_model()
    user_content = (
        f"Trip:\n{_format_trip(state)}\n\n"
        f"Daily itinerary (spots per day):\n{_format_itinerary(state)}\n\n"
        f"Weather:\n{_format_weather(state)}\n\n"
        f"Xiaohongshu reference notes:\n{_format_xhs_refs(state)}\n\n"
        f"XHS aggregated trends (primary outfit source when present):\n{_format_trends(state)}\n\n"
        "Produce one outfit for each day from start_date to end_date. "
        "Ground outfits in XHS trends when available. "
        "Each day MUST have a different outfit — vary colors and hero pieces by date and spot. "
        "When a day lists multiple scenic spots, design ONE outfit that works at ALL of them "
        "(comfortable walking, photo-ready, weather-appropriate, no outfit change mid-day). "
        "In recommendation_reason, explain how the outfit fits each spot that day by name."
    )

    messages = [
        SystemMessage(content=load_prompt("stylist.md")),
        HumanMessage(content=user_content),
    ]
    stylist_retry_hint = (
        "Your previous reply was null or invalid. "
        'Return ONLY JSON: {"outfits": [{"date": "YYYY-MM-DD", "outfit_summary": "...", '
        '"recommendation_reason": "...", "search_keywords": ["..."]}]} '
        "with one outfit object for each trip day."
    )

    try:
        result: StylistOutput = invoke_structured(
            model,
            StylistOutput,
            messages,
            retries=1,
            retry_hint=stylist_retry_hint,
            operation="stylist_plan",
        )
        if not result.outfits:
            result = invoke_structured(
                model,
                StylistOutput,
                [*messages, HumanMessage(content=stylist_retry_hint)],
                operation="stylist_plan_retry",
            )
    except OutputParserException as exc:
        msg = f"穿搭规划解析失败：{exc}"
        return state.append_error(msg).append_trace("Stylist", msg, level="error")

    if not result.outfits:
        msg = "穿搭规划失败：模型未返回有效穿搭方案，请稍后重试"
        return state.append_error(msg).append_trace("Stylist", msg, level="error")

    outfits = sorted(result.outfits, key=lambda item: item.date)
    state = state.append_trace("Stylist", f"planned {len(outfits)} outfit(s)")
    return state.model_copy(update={"outfits": outfits})
