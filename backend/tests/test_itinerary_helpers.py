"""Tests for day_all_spots helper."""

from datetime import date

from src.graph.state import DayItinerary
from src.services.itinerary import day_all_spots


def test_day_all_spots_deduplicates_slots() -> None:
    row = DayItinerary(
        date=date(2026, 6, 8),
        spot_names=["洱海生态廊道", "大理古城"],
        morning="洱海生态廊道",
        afternoon="大理古城",
    )
    assert day_all_spots(row) == ["洱海生态廊道", "大理古城"]
