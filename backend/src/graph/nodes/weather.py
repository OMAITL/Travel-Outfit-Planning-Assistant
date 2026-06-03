"""Weather Agent node — fetch daily forecasts for the trip."""

from __future__ import annotations

from src.graph.state import DailyWeather, PlanningPhase, PlanningState
from src.tools.weather import fetch_daily_weather


def weather_node(state: PlanningState) -> PlanningState:
    if state.trip is None or not state.trip.is_complete:
        return state.append_trace("Weather", "skipped: trip not ready", level="warning")

    trip = state.trip
    state = state.append_trace(
        "Weather",
        f"fetching forecast for {trip.destination} ({trip.start_date} ~ {trip.end_date})",
    )

    try:
        weather: list[DailyWeather] = fetch_daily_weather(
            trip.destination,
            trip.start_date,
            trip.end_date,
        )
    except (ValueError, OSError) as exc:
        return (
            state.append_error(f"Weather API failed: {exc}")
            .append_trace("Weather", f"degraded: {exc}", level="warning")
            .model_copy(update={"weather": [], "phase": PlanningPhase.PLANNING})
        )

    if not weather:
        state = state.append_error(
            f"No weather data returned for {trip.destination}; stylist will use seasonal fallback"
        ).append_trace("Weather", "no forecast rows in date range", level="warning")
    else:
        state = state.append_trace("Weather", f"loaded {len(weather)} day(s)")

    return state.model_copy(update={"weather": weather, "phase": PlanningPhase.PLANNING})
