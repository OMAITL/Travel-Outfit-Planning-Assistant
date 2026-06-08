"""Itinerary Agent — AI travel planner with rule seeding and route scoring."""

from __future__ import annotations

from src.graph.state import PlanningState
from src.services.itinerary_planner import plan_itinerary_from_state


def itinerary_node(state: PlanningState, *, llm=None) -> PlanningState:
    if state.trip is None or not state.trip.is_complete:
        return state.append_trace("Itinerary", "skipped: trip not ready", level="warning")

    prefs = state.trip.preferences
    if prefs.plan_mode == "manual":
        return state.append_trace("Itinerary", "skipped: manual plan mode")

    user_spots = list(prefs.spot_names or [])
    state = state.append_trace(
        "Itinerary",
        f"AI planner: {len(user_spots)} spot(s), {state.trip.trip_days} day(s)",
    )

    rows, scored, trace = plan_itinerary_from_state(state, llm=llm, use_llm=True)
    state = state.append_trace("Itinerary", trace)
    if scored and scored.route.name:
        state = state.append_trace(
            "Itinerary",
            f"route={scored.route.name} total_score={scored.breakdown.total:.3f}",
        )
    return state.model_copy(update={"itinerary": rows})
