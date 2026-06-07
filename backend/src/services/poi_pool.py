"""Build and distribute a POI pool for multi-day trips.

Only user-selected scenic spots are used. A spot may span multiple half-days
(e.g. 6/6–6/7 morning at 古城, then 6/7 afternoon–6/8 at 洱海).
"""

from __future__ import annotations

from datetime import date

from src.graph.state import DayItinerary


def build_poi_pool(
    *,
    user_spot_names: list[str],
    destination: str = "",
    day_count: int = 0,
    extra_poi_names: list[str] | None = None,
) -> list[str]:
    """Return deduplicated user-selected spots in pick order (no auto-expansion)."""
    del destination, day_count  # kept for call-site compatibility
    pool: list[str] = []
    seen: set[str] = set()
    for name in [*user_spot_names, *(extra_poi_names or [])]:
        cleaned = name.strip()
        if cleaned and cleaned not in seen:
            pool.append(cleaned)
            seen.add(cleaned)
    return pool


def _contiguous_slot_assignment(pool: list[str], slot_count: int) -> list[str]:
    """Split timeline slots into contiguous blocks per selected spot."""
    if slot_count <= 0:
        return []
    if not pool:
        return [""] * slot_count

    base, extra = divmod(slot_count, len(pool))
    assigned: list[str] = []
    for index, spot in enumerate(pool):
        block = base + (1 if index < extra else 0)
        assigned.extend([spot] * block)
    return assigned[:slot_count]


def distribute_poi_pool(
    poi_pool: list[str],
    dates: list[date],
    *,
    include_evening: bool | None = None,
) -> list[DayItinerary]:
    """
    Assign morning / afternoon (and optional evening) using contiguous blocks.

    With 2 spots and 3 days, typical result for [古城, 洱海]:
    - 6/6 AM+PM, 6/7 AM → 古城
    - 6/7 PM, 6/8 AM+PM → 洱海
    """
    del include_evening  # evening only when explicitly requested later
    if not dates:
        return []

    timeline: list[tuple[date, str]] = []
    for day in dates:
        timeline.append((day, "morning"))
        timeline.append((day, "afternoon"))

    assignments = _contiguous_slot_assignment(poi_pool, len(timeline))

    day_map: dict[date, dict[str, str | None]] = {
        day: {"morning": None, "afternoon": None, "evening": None} for day in dates
    }
    day_spots: dict[date, list[str]] = {day: [] for day in dates}

    for (day, period), spot in zip(timeline, assignments, strict=False):
        if not spot:
            continue
        day_map[day][period] = spot
        if spot not in day_spots[day]:
            day_spots[day].append(spot)

    rows: list[DayItinerary] = []
    for day in dates:
        slots = day_map[day]
        rows.append(
            DayItinerary(
                date=day,
                spot_names=day_spots[day],
                morning=slots["morning"],
                afternoon=slots["afternoon"],
                evening=slots["evening"],
            )
        )
    return rows


def plan_auto_itinerary(
    *,
    user_spot_names: list[str],
    destination: str,
    dates: list[date],
    extra_poi_names: list[str] | None = None,
) -> tuple[list[str], list[DayItinerary]]:
    """Build user-only POI pool and distribute across trip half-day slots."""
    pool = build_poi_pool(
        user_spot_names=user_spot_names,
        destination=destination,
        day_count=len(dates),
        extra_poi_names=extra_poi_names,
    )
    rows = distribute_poi_pool(pool, dates)
    return pool, rows
