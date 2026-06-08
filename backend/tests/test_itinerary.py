"""Tests for scenic spot itinerary allocation."""

from datetime import date

from src.services.itinerary import assign_spots_auto, build_itinerary


def test_assign_spots_auto_plans_by_region() -> None:
    dates = [date(2026, 6, 5), date(2026, 6, 6), date(2026, 6, 7)]
    rows = assign_spots_auto(["洱海生态廊道", "大理古城"], dates, destination="大理")
    assert len(rows) == 3
    allowed = {"洱海生态廊道", "大理古城"}
    for row in rows:
        for spot in [*row.spot_names, row.morning, row.afternoon, row.evening]:
            if spot:
                assert spot in allowed


def test_build_itinerary_manual_mode() -> None:
    rows = build_itinerary(
        start_date=date(2026, 6, 5),
        end_date=date(2026, 6, 6),
        spot_names=["洱海生态廊道", "大理古城"],
        destination="大理",
        plan_mode="manual",
        daily_spot_names=[["洱海生态廊道"], ["大理古城"]],
    )
    assert rows[0].spot_names == ["洱海生态廊道"]
    assert rows[1].spot_names == ["大理古城"]
