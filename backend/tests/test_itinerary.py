"""Tests for scenic spot itinerary allocation."""

from datetime import date

from src.services.itinerary import assign_spots_auto, build_itinerary


def test_assign_spots_auto_round_robin() -> None:
    dates = [date(2026, 6, 5), date(2026, 6, 6), date(2026, 6, 7)]
    rows = assign_spots_auto(["洱海生态廊道", "大理古城"], dates)
    assert rows[0].spot_names == ["洱海生态廊道"]
    assert rows[1].spot_names == ["大理古城"]
    assert rows[2].spot_names == []


def test_build_itinerary_manual_mode() -> None:
    rows = build_itinerary(
        start_date=date(2026, 6, 5),
        end_date=date(2026, 6, 6),
        spot_names=["洱海生态廊道", "大理古城"],
        plan_mode="manual",
        daily_spot_names=[["洱海生态廊道"], ["大理古城"]],
    )
    assert rows[0].spot_names == ["洱海生态廊道"]
    assert rows[1].spot_names == ["大理古城"]
