"""Tests for XHS inspiration backfill and per-day note count."""

from datetime import date

from src.graph.nodes.inspiration import _ensure_notes_per_day
from src.graph.state import DayItinerary, OutfitInspiration


def _note(note_id: str, *, day: date, likes: int, keyword: str) -> OutfitInspiration:
    return OutfitInspiration(
        trip_date=day,
        note_id=note_id,
        title=f"note {note_id}",
        cover_url="https://xhs.example/cover.jpg",
        note_url=f"https://xhs.example/note/{note_id}",
        search_keyword=keyword,
        liked_count=likes,
    )


def test_ensure_notes_per_day_pads_to_three() -> None:
    day1 = date(2026, 6, 8)
    day2 = date(2026, 6, 9)
    refs = [
        _note("a", day=day1, likes=1200, keyword="洱海生态廊道 穿搭"),
        _note("b", day=day1, likes=900, keyword="洱海生态廊道 拍照穿搭"),
        _note("c", day=day1, likes=850, keyword="洱海生态廊道 ootd"),
        _note("d", day=day2, likes=800, keyword="大理古城 穿搭"),
        _note("e", day=day2, likes=750, keyword="大理古城 ootd"),
        _note("f", day=day2, likes=700, keyword="大理古城 拍照穿搭"),
    ]
    days = [
        DayItinerary(date=day1, spot_names=["洱海生态廊道", "大理古城"]),
        DayItinerary(date=day2, spot_names=["大理古城"]),
    ]
    filled = _ensure_notes_per_day(refs, days, "大理", target_per_day=3)
    by_date: dict[date, list[OutfitInspiration]] = {}
    for ref in filled:
        by_date.setdefault(ref.trip_date, []).append(ref)
    assert len(by_date[day1]) == 3
    assert len(by_date[day2]) == 3
    assert len(by_date[day2]) == 3


def test_ensure_notes_per_day_keeps_partial_days() -> None:
    day1 = date(2026, 6, 8)
    refs = [_note("a", day=day1, likes=100, keyword="洱海 穿搭")]
    days = [DayItinerary(date=day1, spot_names=["洱海生态廊道"])]
    filled = _ensure_notes_per_day(refs, days, "大理", target_per_day=3)
    assert len(filled) == 1
    assert filled[0].note_id == "a"


def test_ensure_notes_per_day_no_cross_day_reuse() -> None:
    day1 = date(2026, 6, 8)
    day2 = date(2026, 6, 9)
    ref = _note("a", day=day1, likes=1200, keyword="洱海生态廊道 穿搭")
    days = [
        DayItinerary(date=day1, spot_names=["洱海生态廊道"]),
        DayItinerary(date=day2, spot_names=["大理古城"]),
    ]
    filled = _ensure_notes_per_day([ref], days, "大理", target_per_day=1)
    day2_refs = [row for row in filled if row.trip_date == day2]
    assert day2_refs == []
