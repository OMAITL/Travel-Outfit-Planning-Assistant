"""Tests for user-only POI pool and contiguous slot distribution."""

from datetime import date

from src.services.itinerary import assign_spots_auto, build_itinerary
from src.services.poi_pool import build_poi_pool, distribute_poi_pool, plan_auto_itinerary


def test_build_poi_pool_uses_user_spots_only() -> None:
    pool = build_poi_pool(
        user_spot_names=["洱海生态廊道", "大理古城"],
        destination="大理",
        day_count=3,
    )
    assert pool == ["洱海生态廊道", "大理古城"]


def test_contiguous_blocks_two_spots_three_days() -> None:
    dates = [date(2026, 6, 6), date(2026, 6, 7), date(2026, 6, 8)]
    pool = ["大理古城", "洱海生态廊道"]
    rows = distribute_poi_pool(pool, dates)
    assert rows[0].morning == "大理古城"
    assert rows[0].afternoon == "大理古城"
    assert rows[1].morning == "大理古城"
    assert rows[1].afternoon == "洱海生态廊道"
    assert rows[2].morning == "洱海生态廊道"
    assert rows[2].afternoon == "洱海生态廊道"
    assert all(
        spot in pool
        for row in rows
        for spot in [row.morning, row.afternoon]
        if spot
    )


def test_assign_spots_auto_no_unselected_catalog_spots() -> None:
    dates = [date(2026, 6, 6), date(2026, 6, 7), date(2026, 6, 8)]
    rows = assign_spots_auto(["洱海生态廊道", "大理古城"], dates, destination="大理")
    allowed = {"洱海生态廊道", "大理古城"}
    for row in rows:
        for spot in [row.morning, row.afternoon, *row.spot_names]:
            if spot:
                assert spot in allowed


def test_plan_auto_itinerary_preserves_user_order() -> None:
    dates = [date(2026, 6, 6), date(2026, 6, 7)]
    pool, rows = plan_auto_itinerary(
        user_spot_names=["洱海生态廊道", "大理古城"],
        destination="大理",
        dates=dates,
    )
    assert pool == ["洱海生态廊道", "大理古城"]
    assert rows[0].morning == "洱海生态廊道"
    assert rows[1].afternoon == "大理古城"


def test_assign_spots_auto_clusters_by_region() -> None:
    dates = [date(2026, 6, 6), date(2026, 6, 7)]
    rows = assign_spots_auto(
        ["大理古城", "崇圣寺三塔", "洱海生态廊道"],
        dates,
        destination="大理",
    )
    day_spots = [s for row in rows for s in row.spot_names]
    assert "大理古城" in day_spots
    assert "崇圣寺三塔" in day_spots
    assert "洱海生态廊道" in day_spots


def test_build_itinerary_manual_mode_keeps_user_slots() -> None:
    rows = build_itinerary(
        start_date=date(2026, 6, 5),
        end_date=date(2026, 6, 6),
        spot_names=["洱海生态廊道", "大理古城"],
        destination="大理",
        plan_mode="manual",
        daily_spot_names=[["洱海生态廊道", "大理古城"], ["崇圣寺三塔"]],
    )
    assert rows[0].morning == "洱海生态廊道"
    assert rows[0].afternoon == "大理古城"
    assert rows[1].morning == "崇圣寺三塔"
