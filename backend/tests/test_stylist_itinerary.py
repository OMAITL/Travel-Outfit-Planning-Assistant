"""Tests for multi-spot itinerary formatting in stylist."""

from datetime import date

from src.graph.nodes.stylist import _format_itinerary
from src.graph.state import DayItinerary, PlanningState, TripContext, TripPreferences


def test_format_itinerary_marks_multi_spot_days() -> None:
    state = PlanningState(
        trip=TripContext(
            destination="大理",
            start_date=date(2026, 6, 8),
            end_date=date(2026, 6, 8),
            preferences=TripPreferences(),
            is_complete=True,
        ),
        itinerary=[
            DayItinerary(
                date=date(2026, 6, 8),
                spot_names=["洱海生态廊道", "大理古城"],
                morning="洱海生态廊道",
                afternoon="大理古城",
            )
        ],
    )
    text = _format_itinerary(state)
    assert "同时适配" in text
    assert "洱海生态廊道" in text
    assert "大理古城" in text
