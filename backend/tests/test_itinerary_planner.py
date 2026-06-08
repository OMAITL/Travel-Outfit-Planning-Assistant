"""Tests for AI travel planner — rules, scoring, and itinerary conversion."""

from __future__ import annotations

from datetime import date

from src.data.spot_profiles import get_spot_profile, resolve_spot_profiles
from src.graph.state import DailyWeather, WeatherCondition
from src.services.itinerary import assign_spots_auto
from src.services.itinerary_rules import (
    generate_rule_route_variants,
    plan_rule_route,
    route_draft_to_itinerary,
)
from src.services.itinerary_planner import plan_itinerary_simple
from src.services.route_scorer import pick_best_route


def _dali_weather() -> dict[date, DailyWeather]:
    return {
        date(2026, 6, 6): DailyWeather(
            date=date(2026, 6, 6),
            temp_min=17,
            temp_max=28,
            condition=WeatherCondition.SUNNY,
            rain_prob=10,
        ),
        date(2026, 6, 7): DailyWeather(
            date=date(2026, 6, 7),
            temp_min=18,
            temp_max=29,
            condition=WeatherCondition.CLOUDY,
            rain_prob=20,
        ),
        date(2026, 6, 8): DailyWeather(
            date=date(2026, 6, 8),
            temp_min=19,
            temp_max=30,
            condition=WeatherCondition.RAINY,
            rain_prob=70,
        ),
    }


def test_spot_profiles_have_required_fields() -> None:
    profile = get_spot_profile("洱海生态廊道")
    assert profile is not None
    assert profile.duration_hours == 4.0
    assert profile.region == "洱海片区"
    assert profile.sunset is True
    assert profile.photo is True
    assert 1 <= profile.popularity <= 5


def test_lijiang_equal_spots_one_per_day() -> None:
    dates = [date(2026, 6, 9), date(2026, 6, 10), date(2026, 6, 11)]
    route = plan_rule_route(
        ["丽江古城", "玉龙雪山", "拉市海"],
        dates,
        destination="丽江",
        weather_by_date=_dali_weather(),
    )
    assert len(route.days) == 3
    for day in route.days:
        assert len(day.spots) == 1
        assert day.use_time_slots is False
    all_spots = {s for day in route.days for s in day.spots}
    assert all_spots == {"丽江古城", "玉龙雪山", "拉市海"}


def test_pack_mode_fills_every_day() -> None:
    dates = [date(2026, 6, 6), date(2026, 6, 7)]
    route = plan_rule_route(
        ["大理古城", "崇圣寺三塔", "洱海生态廊道"],
        dates,
        destination="大理",
    )
    assert all(day.spots for day in route.days)


def test_spread_mode_two_spots_three_days() -> None:
    dates = [date(2026, 6, 6), date(2026, 6, 7), date(2026, 6, 8)]
    route = plan_rule_route(
        ["洱海生态廊道", "大理古城"],
        dates,
        destination="大理",
    )
    assert len(route.days) == 3
    assert all(day.spots for day in route.days)
    profiles = {p.name: p for p in resolve_spot_profiles(["洱海生态廊道", "大理古城"], destination="大理")}
    rows = route_draft_to_itinerary(route, profiles)
    assert rows[0].spot_names


def test_equal_mode_no_time_slots_in_itinerary() -> None:
    dates = [date(2026, 6, 9), date(2026, 6, 10), date(2026, 6, 11)]
    route = plan_rule_route(["丽江古城", "玉龙雪山", "拉市海"], dates, destination="丽江")
    profiles = {p.name: p for p in resolve_spot_profiles(["丽江古城", "玉龙雪山", "拉市海"], destination="丽江")}
    rows = route_draft_to_itinerary(route, profiles)
    for row in rows:
        assert row.morning is None
        assert row.afternoon is None
        assert row.evening is None
        assert len(row.spot_names) == 1


def test_pack_mode_same_region_spots_share_day() -> None:
    dates = [date(2026, 6, 6), date(2026, 6, 7)]
    route = plan_rule_route(
        ["大理古城", "崇圣寺三塔", "洱海生态廊道"],
        dates,
        destination="大理",
        weather_by_date=_dali_weather(),
    )
    all_assigned = {s for day in route.days for s in day.spots}
    assert all_assigned == {"大理古城", "崇圣寺三塔", "洱海生态廊道"}
    assert all(day.spots for day in route.days)
    assert any(
        "大理古城" in day.spots and "崇圣寺三塔" in day.spots
        for day in route.days
    )


def test_rule_route_respects_duration_cap() -> None:
    dates = [date(2026, 6, 6)]
    route = plan_rule_route(
        ["洱海生态廊道", "双廊古镇", "喜洲古镇"],
        dates,
        destination="大理",
    )
    profiles = {p.name: p for p in resolve_spot_profiles(route.days[0].spots, destination="大理")}
    hours = sum(profiles[s].duration_hours for s in route.days[0].spots if s in profiles)
    assert hours <= 8.5


def test_route_scorer_picks_best_of_three() -> None:
    dates = [date(2026, 6, 6), date(2026, 6, 7)]
    variants = generate_rule_route_variants(
        ["大理古城", "崇圣寺三塔", "洱海生态廊道"],
        dates,
        destination="大理",
        weather_by_date=_dali_weather(),
    )
    profiles = {p.name: p for p in resolve_spot_profiles(
        ["大理古城", "崇圣寺三塔", "洱海生态廊道"], destination="大理"
    )}
    best = pick_best_route(variants, profiles=profiles, weather_by_date=_dali_weather(), preferences=None)
    assert best.route.name in {"Route A", "Route B", "Route C"}
    assert best.breakdown.total > 0


def test_assign_spots_auto_uses_only_user_spots() -> None:
    dates = [date(2026, 6, 6), date(2026, 6, 7), date(2026, 6, 8)]
    rows = assign_spots_auto(
        ["洱海生态廊道", "大理古城"],
        dates,
        destination="大理",
        weather_by_date=_dali_weather(),
    )
    allowed = {"洱海生态廊道", "大理古城"}
    for row in rows:
        for spot in [*row.spot_names, row.morning, row.afternoon, row.evening]:
            if spot:
                assert spot in allowed


def test_plan_itinerary_simple_sets_plan_reason() -> None:
    dates = [date(2026, 6, 6), date(2026, 6, 7)]
    rows = plan_itinerary_simple(
        ["大理古城", "崇圣寺三塔"],
        dates,
        destination="大理",
        weather_by_date=_dali_weather(),
    )
    assert rows[0].spot_names
    assert rows[0].plan_reason


def test_route_draft_to_itinerary_time_slots() -> None:
    from src.services.itinerary_rules import DayPlanDraft, RouteDraft

    profiles = {p.name: p for p in resolve_spot_profiles(["锦里古街", "宽窄巷子"], destination="成都")}
    route = RouteDraft(
        name="Test",
        days=[
            DayPlanDraft(
                date=date(2026, 6, 9),
                spots=["宽窄巷子", "锦里古街"],
                reason="同城顺路",
            )
        ],
    )
    rows = route_draft_to_itinerary(route, profiles)
    assert rows[0].morning
    assert rows[0].evening == "锦里古街" or rows[0].afternoon == "锦里古街"
