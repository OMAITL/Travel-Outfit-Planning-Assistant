"""Stylist Agent node — LLM outfit planning from trip + weather."""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.graph.state import DailyOutfit, PlanningState
from src.services.llm import get_chat_model, invoke_structured, load_prompt


class StylistOutput(BaseModel):
    outfits: list[DailyOutfit] = Field(default_factory=list)


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


def _format_trip(state: PlanningState) -> str:
    trip = state.trip
    if trip is None:
        return "Trip context unavailable."
    prefs = trip.preferences
    return json.dumps(
        {
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
            "budget_per_item": prefs.budget_per_item,
            "budget_total": prefs.budget_total,
        },
        ensure_ascii=False,
    )


def stylist_node(state: PlanningState, *, llm=None) -> PlanningState:
    if state.trip is None or not state.trip.is_complete:
        return state.append_trace("Stylist", "skipped: trip not ready", level="warning")

    state = state.append_trace("Stylist", "planning daily outfits")
    model = llm or get_chat_model()
    user_content = (
        f"Trip:\n{_format_trip(state)}\n\n"
        f"Weather:\n{_format_weather(state)}\n\n"
        "Produce one outfit for each day from start_date to end_date."
    )

    result: StylistOutput = invoke_structured(
        model,
        StylistOutput,
        [
            SystemMessage(content=load_prompt("stylist.md")),
            HumanMessage(content=user_content),
        ],
    )

    outfits = sorted(result.outfits, key=lambda item: item.date)
    state = state.append_trace("Stylist", f"planned {len(outfits)} outfit(s)")
    return state.model_copy(update={"outfits": outfits})
