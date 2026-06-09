"""Tests for tiered XHS search ladder in inspiration node."""

from datetime import date
from unittest.mock import patch

from src.graph.nodes.inspiration import _collect_day_notes_tiered, _profiles_for_day_spots
from src.graph.state import TripPreferences
from src.services.outfit_query_compiler import profile_from_preferences
from src.tools.justone_xhs import XhsNoteSummary


def _note(note_id: str, *, title: str = "大理古城穿搭分享") -> XhsNoteSummary:
    return XhsNoteSummary(
        note_id=note_id,
        title=title,
        cover_url="https://xhs.example/c.jpg",
        liked_count=100,
    )


def test_tiered_search_escalates_when_broad_tier_returns_nothing() -> None:
    prefs = TripPreferences(gender="女", style="拍照出片", body_type="梨型")
    profile = profile_from_preferences(
        prefs,
        destination="大理",
        spot="大理古城",
        trip_date=date(2026, 6, 9),
    )
    calls: list[str] = []

    def fake_search(keyword: str, **kwargs):
        calls.append(keyword)
        if keyword == "大理古城 穿搭":
            return [_note("1")]
        return []

    with patch("src.graph.nodes.inspiration.search_xhs_notes", side_effect=fake_search):
        notes, used, tried, traces = _collect_day_notes_tiered(
            [profile],
            max_notes=3,
            fetch_detail=False,
            max_api_calls=10,
            min_liked=0,
            stop_after_notes=1,
        )

    assert len(notes) == 1
    assert "大理古城 穿搭" in tried
    assert any("一级-景点宽泛" in line for line in traces)
    assert calls[0] == "大理古城 穿搭"


def test_tiered_search_runs_city_tier_when_spot_tiers_empty() -> None:
    prefs = TripPreferences(gender="女", style="拍照出片", body_type="梨型")
    profiles = _profiles_for_day_spots(
        destination="大理",
        spots=["大理古城"],
        prefs=prefs,
        trip_date=date(2026, 6, 9),
    )

    def fake_search(keyword: str, **kwargs):
        if keyword.startswith("大理"):
            return [_note("city", title=f"{keyword} ootd 穿搭")]
        return []

    with patch("src.graph.nodes.inspiration.search_xhs_notes", side_effect=fake_search):
        notes, _used, _tried, traces = _collect_day_notes_tiered(
            profiles,
            max_notes=1,
            fetch_detail=False,
            max_api_calls=20,
            min_liked=0,
            stop_after_notes=1,
        )

    assert len(notes) == 1
    assert any("三级-城市" in line or "一级" in line for line in traces)
