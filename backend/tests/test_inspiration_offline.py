"""Tests for offline XHS fallback when API token is missing."""

from datetime import date

from src.graph.nodes.inspiration import inspiration_node
from src.graph.state import DayItinerary, PlanningPhase, PlanningState, TripContext, TripPreferences


def test_inspiration_without_token_still_returns_search_links(monkeypatch) -> None:
    from src.config import get_settings

    settings = get_settings().model_copy(update={"justoneapi_token": None})
    monkeypatch.setattr("src.graph.nodes.inspiration.get_settings", lambda: settings)

    state = PlanningState(
        phase=PlanningPhase.PLANNING,
        trip=TripContext(
            destination="丽江",
            start_date=date(2026, 6, 10),
            end_date=date(2026, 6, 10),
            preferences=TripPreferences(
                style="温柔",
                gender="女",
                body_type="微胖",
                height_cm=165,
                weight_kg=90,
                spot_names=["丽江古城"],
            ),
            is_complete=True,
        ),
        itinerary=[DayItinerary(date=date(2026, 6, 10), spot_names=["丽江古城"])],
    )
    result = inspiration_node(state)
    assert result.outfit_inspirations
    assert all(ref.is_search_link for ref in result.outfit_inspirations)
    assert any("丽江" in (ref.search_keyword or "") for ref in result.outfit_inspirations)
    assert result.xhs_query_debug
    assert result.xhs_query_debug[0].final_query
