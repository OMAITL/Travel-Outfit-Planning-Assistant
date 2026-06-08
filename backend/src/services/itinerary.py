"""Assign selected scenic spots to each trip day."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from src.graph.state import DailyWeather, DayItinerary
from src.services.itinerary_planner import plan_itinerary_simple
from src.services.poi_pool import distribute_poi_pool


def iter_trip_dates(start_date: date, end_date: date) -> list[date]:
    dates: list[date] = []
    current = start_date
    while current <= end_date:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def assign_spots_auto(
    spot_names: list[str],
    dates: list[date],
    *,
    destination: str = "",
    extra_poi_names: list[str] | None = None,
    weather_by_date: dict[date, DailyWeather] | None = None,
    preferences: dict[str, object] | None = None,
) -> list[DayItinerary]:
    """Rule/AI travel planner — geographic clustering with duration & weather constraints."""
    del preferences  # used in full workflow planner; preview uses rule scoring defaults
    merged: list[str] = []
    seen: set[str] = set()
    for name in [*spot_names, *(extra_poi_names or [])]:
        cleaned = name.strip()
        if cleaned and cleaned not in seen:
            merged.append(cleaned)
            seen.add(cleaned)
    return plan_itinerary_simple(
        merged,
        dates,
        destination=destination,
        weather_by_date=weather_by_date,
    )


def assign_spots_manual(
    dates: list[date],
    daily_spot_names: list[list[str]] | None,
) -> list[DayItinerary]:
    """Use user-specified per-day spot lists with AM/PM/evening slots when provided."""
    rows = daily_spot_names or []
    itinerary: list[DayItinerary] = []
    for index, day in enumerate(dates):
        names = rows[index] if index < len(rows) else []
        cleaned = [name.strip() for name in names if name.strip()]
        morning = cleaned[0] if len(cleaned) >= 1 else None
        afternoon = cleaned[1] if len(cleaned) >= 2 else None
        evening = cleaned[2] if len(cleaned) >= 3 else None
        itinerary.append(
            DayItinerary(
                date=day,
                spot_names=cleaned,
                morning=morning,
                afternoon=afternoon,
                evening=evening,
            )
        )
    return itinerary


def build_itinerary(
    *,
    start_date: date,
    end_date: date,
    spot_names: list[str] | None = None,
    destination: str | None = None,
    plan_mode: Literal["auto", "manual"] = "auto",
    daily_spot_names: list[list[str]] | None = None,
    extra_poi_names: list[str] | None = None,
) -> list[DayItinerary]:
    dates = iter_trip_dates(start_date, end_date)
    if plan_mode == "manual":
        return assign_spots_manual(dates, daily_spot_names)
    return assign_spots_auto(
        spot_names or [],
        dates,
        destination=destination or "",
        extra_poi_names=extra_poi_names,
    )


def redistribute_itinerary(
    itinerary: list[DayItinerary],
    poi_pool: list[str],
) -> list[DayItinerary]:
    """Re-run slot distribution when the POI pool grows (e.g. after LLM expansion)."""
    dates = [row.date for row in itinerary]
    return distribute_poi_pool(poi_pool, dates)


def day_all_spots(row: DayItinerary) -> list[str]:
    """Ordered unique scenic spots scheduled on one day (AM/PM/evening + spot_names)."""
    ordered: list[str] = []
    seen: set[str] = set()
    for name in [*row.spot_names, row.morning, row.afternoon, row.evening]:
        cleaned = str(name or "").strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            ordered.append(cleaned)
    return ordered
