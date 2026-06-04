"""Assign selected scenic spots to each trip day."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from src.graph.state import DayItinerary


def iter_trip_dates(start_date: date, end_date: date) -> list[date]:
    dates: list[date] = []
    current = start_date
    while current <= end_date:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def assign_spots_auto(spot_names: list[str], dates: list[date]) -> list[DayItinerary]:
    """Round-robin distribute spots across days (matches Vue autoAssignDays)."""
    if not dates:
        return []
    buckets: dict[date, list[str]] = {day: [] for day in dates}
    cleaned = [name.strip() for name in spot_names if name.strip()]
    for index, spot in enumerate(cleaned):
        buckets[dates[index % len(dates)]].append(spot)
    return [DayItinerary(date=day, spot_names=buckets[day]) for day in dates]


def assign_spots_manual(
    dates: list[date],
    daily_spot_names: list[list[str]] | None,
) -> list[DayItinerary]:
    """Use user-specified per-day spot lists."""
    rows = daily_spot_names or []
    itinerary: list[DayItinerary] = []
    for index, day in enumerate(dates):
        names = rows[index] if index < len(rows) else []
        cleaned = [name.strip() for name in names if name.strip()]
        itinerary.append(DayItinerary(date=day, spot_names=cleaned))
    return itinerary


def build_itinerary(
    *,
    start_date: date,
    end_date: date,
    spot_names: list[str] | None = None,
    plan_mode: Literal["auto", "manual"] = "auto",
    daily_spot_names: list[list[str]] | None = None,
) -> list[DayItinerary]:
    dates = iter_trip_dates(start_date, end_date)
    if plan_mode == "manual":
        return assign_spots_manual(dates, daily_spot_names)
    return assign_spots_auto(spot_names or [], dates)
