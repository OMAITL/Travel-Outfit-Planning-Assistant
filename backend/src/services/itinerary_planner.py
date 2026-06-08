"""AI Travel Planner — rule seeding, LLM routes, scoring & selection."""

from __future__ import annotations

import json
from datetime import date, timedelta

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, field_validator

from src.data.spot_profiles import (
    CityAnchor,
    get_city_anchor,
    profiles_as_dicts,
    resolve_spot_profiles,
)
from src.graph.state import DailyWeather, DayItinerary, PlanningState, TripContext
from src.services.itinerary_rules import (
    DayPlanDraft,
    RouteDraft,
    generate_rule_route_variants,
    route_draft_to_itinerary,
)
from src.services.llm import get_chat_model, invoke_structured, load_prompt
from src.services.route_scorer import ScoredRoute, pick_best_route


class PlannerDayOut(BaseModel):
    date: date
    spots: list[str] = Field(default_factory=list)
    reason: str = ""


class PlannerRouteOut(BaseModel):
    name: str
    days: list[PlannerDayOut] = Field(default_factory=list)


class PlannerOutput(BaseModel):
    routes: list[PlannerRouteOut] = Field(default_factory=list)

    @field_validator("routes", mode="before")
    @classmethod
    def _normalize_routes(cls, value: object) -> object:
        if value is None:
            return []
        return value


def _iter_trip_dates(start_date: date, end_date: date) -> list[date]:
    dates: list[date] = []
    current = start_date
    while current <= end_date:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def _weather_map(state: PlanningState) -> dict[date, DailyWeather]:
    return {row.date: row for row in state.weather}


def _preferences_dict(trip: TripContext) -> dict[str, object]:
    prefs = trip.preferences
    return {
        "activities": prefs.activities,
        "style": prefs.style,
        "gender": prefs.gender,
        "avoid_items": prefs.avoid_items,
    }


def _format_weather(weather_by_date: dict[date, DailyWeather], dates: list[date]) -> str:
    lines: list[str] = []
    for day in dates:
        w = weather_by_date.get(day)
        if w is None:
            lines.append(f"- {day}: 无预报")
            continue
        cond = w.condition.value if hasattr(w.condition, "value") else w.condition
        lines.append(f"- {day}: {cond}, {w.temp_min:.0f}~{w.temp_max:.0f}°C, 降水概率 {w.rain_prob or 0:.0f}%")
    return "\n".join(lines) if lines else "无天气预报"


def _format_rule_hints(variants: list[RouteDraft]) -> str:
    chunks: list[str] = []
    for route in variants:
        day_lines = []
        for day in route.days:
            spots = "、".join(day.spots) if day.spots else "（休息/自由活动）"
            day_lines.append(f"  {day.date}: {spots} — {day.reason}")
        chunks.append(f"{route.name}:\n" + "\n".join(day_lines))
    return "\n\n".join(chunks)


def _sanitize_llm_routes(
    output: PlannerOutput,
    *,
    allowed_spots: set[str],
    dates: list[date],
) -> list[RouteDraft]:
    routes: list[RouteDraft] = []
    date_set = set(dates)
    for route in output.routes[:3]:
        days: list[DayPlanDraft] = []
        for day in route.days:
            if day.date not in date_set:
                continue
            spots = [s for s in day.spots if s in allowed_spots]
            days.append(DayPlanDraft(date=day.date, spots=spots, reason=day.reason))
        for d in dates:
            if d not in {x.date for x in days}:
                days.append(DayPlanDraft(date=d, spots=[], reason=""))
        days.sort(key=lambda x: x.date)
        routes.append(RouteDraft(name=route.name or "Route", days=days))
    return routes


def _invoke_llm_routes(
    *,
    trip: TripContext,
    dates: list[date],
    spot_names: list[str],
    profiles_payload: list[dict[str, object]],
    weather_by_date: dict[date, DailyWeather],
    rule_variants: list[RouteDraft],
    anchor: CityAnchor | None,
    llm=None,
) -> list[RouteDraft] | None:
    model = llm or get_chat_model()
    system = load_prompt("itinerary.md")
    user_payload = {
        "destination": trip.destination,
        "dates": [str(d) for d in dates],
        "trip_days": len(dates),
        "user_selected_spots": spot_names,
        "spot_profiles": profiles_payload,
        "hotel_location": {
            "name": anchor.name if anchor else trip.destination,
            "lat": anchor.lat if anchor else None,
            "lng": anchor.lng if anchor else None,
        },
        "user_profile": _preferences_dict(trip),
        "weather_forecast": _format_weather(weather_by_date, dates),
        "rule_engine_hints": _format_rule_hints(rule_variants),
    }
    messages = [
        SystemMessage(content=system),
        HumanMessage(content=json.dumps(user_payload, ensure_ascii=False, indent=2)),
    ]
    try:
        result = invoke_structured(model, PlannerOutput, messages, retries=1, operation="itinerary_planner")
    except Exception:
        return None
    allowed = set(spot_names)
    routes = _sanitize_llm_routes(result, allowed_spots=allowed, dates=dates)
    return routes if routes else None


def plan_itinerary_from_state(
    state: PlanningState,
    *,
    llm=None,
    use_llm: bool = True,
) -> tuple[list[DayItinerary], ScoredRoute | None, str]:
    """
    Full AI travel planner pipeline.

    Returns (itinerary rows, best scored route metadata, trace summary).
    """
    if state.trip is None:
        return [], None, "skipped: no trip"

    trip = state.trip
    prefs = trip.preferences
    spot_names = list(prefs.spot_names or [])
    dates = _iter_trip_dates(trip.start_date, trip.end_date)
    if not dates:
        return [], None, "skipped: no dates"

    destination = trip.destination
    weather_by_date = _weather_map(state)
    profiles = resolve_spot_profiles(spot_names, destination=destination)
    profile_map = {p.name: p for p in profiles}
    anchor = get_city_anchor(destination)
    preferences = _preferences_dict(trip)

    rule_variants = generate_rule_route_variants(
        spot_names,
        dates,
        destination=destination,
        weather_by_date=weather_by_date,
    )

    candidates: list[RouteDraft] = list(rule_variants)
    llm_used = False
    if use_llm and spot_names:
        llm_routes = _invoke_llm_routes(
            trip=trip,
            dates=dates,
            spot_names=spot_names,
            profiles_payload=profiles_as_dicts(profiles),
            weather_by_date=weather_by_date,
            rule_variants=rule_variants,
            anchor=anchor,
            llm=llm,
        )
        if llm_routes:
            candidates = llm_routes
            llm_used = True

    best = pick_best_route(
        candidates,
        profiles=profile_map,
        weather_by_date=weather_by_date,
        preferences=preferences,
        anchor=anchor,
    )
    rows = route_draft_to_itinerary(best.route, profile_map)

    trace = (
        f"selected {best.route.name} score={best.breakdown.total:.3f} "
        f"(dist={best.breakdown.distance:.2f} weather={best.breakdown.weather:.2f} "
        f"pop={best.breakdown.popularity:.2f} pref={best.breakdown.preference:.2f} "
        f"photo={best.breakdown.photo:.2f}) "
        f"via={'LLM+rules' if llm_used else 'rules-only'}"
    )
    return rows, best, trace


def plan_itinerary_simple(
    spot_names: list[str],
    dates: list[date],
    *,
    destination: str = "",
    weather_by_date: dict[date, DailyWeather] | None = None,
    preferences: dict[str, object] | None = None,
) -> list[DayItinerary]:
    """Rule-based planner for API preview (no LLM / no full state)."""
    del preferences
    from src.services.itinerary_rules import rule_plan_to_itinerary

    return rule_plan_to_itinerary(
        spot_names,
        dates,
        destination=destination,
        weather_by_date=weather_by_date,
    )
