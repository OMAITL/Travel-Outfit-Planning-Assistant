"""Itinerary node — assign user-selected spots across half-day slots."""

from __future__ import annotations

from src.graph.state import PlanningState
from src.services.itinerary import iter_trip_dates
from src.services.poi_pool import plan_auto_itinerary


def itinerary_node(state: PlanningState, *, llm=None) -> PlanningState:
    del llm  # user spots only; no LLM POI expansion
    if state.trip is None or not state.trip.is_complete:
        return state.append_trace("Itinerary", "skipped: trip not ready", level="warning")

    trip = state.trip
    prefs = trip.preferences
    if prefs.plan_mode == "manual":
        return state.append_trace("Itinerary", "skipped: manual plan mode")

    dates = iter_trip_dates(trip.start_date, trip.end_date)
    if not dates:
        return state.append_trace("Itinerary", "skipped: no trip dates", level="warning")

    user_spots = list(prefs.spot_names or [])
    state = state.append_trace(
        "Itinerary",
        f"allocating {len(user_spots)} user spot(s) across {len(dates)} day(s)",
    )

    poi_pool, rows = plan_auto_itinerary(
        user_spot_names=user_spots,
        destination=trip.destination,
        dates=dates,
    )

    state = state.append_trace(
        "Itinerary",
        f"POI pool={poi_pool or 'empty'} → {len(rows)} day(s), AM/PM contiguous blocks",
    )
    return state.model_copy(update={"itinerary": rows})
