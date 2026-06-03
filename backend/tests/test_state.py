import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

import src.graph  # noqa: F401 — triggers PlanningState.model_rebuild()

from src.graph.report import DailyReportCard, TravelReport
from src.graph.state import (
    DailyOutfit,
    DailyWeather,
    PlanningPhase,
    PlanningState,
    ProductCard,
    TripContext,
    WeatherCondition,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "planning_state.json"


def test_trip_context_computes_trip_days() -> None:
    trip = TripContext(
        destination="东京",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 5),
        is_complete=True,
    )
    assert trip.trip_days == 5


def test_trip_context_rejects_invalid_date_range() -> None:
    with pytest.raises(ValidationError):
        TripContext(
            destination="东京",
            start_date=date(2026, 7, 5),
            end_date=date(2026, 7, 1),
        )


def test_daily_weather_normalizes_condition_enum() -> None:
    weather = DailyWeather(
        date=date(2026, 7, 10),
        temp_min=18,
        temp_max=26,
        condition="晴",
    )
    assert weather.condition == WeatherCondition.SUNNY


def test_daily_outfit_strips_empty_keywords() -> None:
    outfit = DailyOutfit(
        date=date(2026, 7, 10),
        outfit_summary="防晒衬衫 + 阔腿裤",
        search_keywords=["  女 防晒 衬衫  ", "", "  "],
    )
    assert outfit.search_keywords == ["女 防晒 衬衫"]


def test_planning_state_round_trip_from_fixture() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    state = PlanningState.model_validate(payload)
    restored = PlanningState.model_validate(state.model_dump(mode="json"))
    assert restored == state
    assert restored.trip is not None
    assert restored.trip.trip_days == 3
    assert restored.phase == PlanningPhase.DONE


def test_planning_state_append_error_and_trace() -> None:
    state = PlanningState()
    state = state.append_error("OneBound quota exceeded")
    state = state.append_trace("Shopping", "degraded to search links", level="warning")
    assert state.errors == ["OneBound quota exceeded"]
    assert len(state.trace) == 1
    assert state.trace[0].level == "warning"


def test_travel_report_daily_card_max_five_products() -> None:
    products = [
        ProductCard(
            title=f"item-{i}",
            pic_url=f"https://img.example/{i}.jpg",
            price=float(i),
            detail_url=f"https://item.taobao.com/item.htm?id={i}",
        )
        for i in range(6)
    ]
    with pytest.raises(ValidationError):
        DailyReportCard(date=date(2026, 7, 10), products=products)


def test_travel_report_builds_from_trip() -> None:
    trip = TripContext(
        destination="大理",
        start_date=date(2026, 7, 10),
        end_date=date(2026, 7, 12),
        is_complete=True,
    )
    report = TravelReport(
        destination=trip.destination,
        start_date=trip.start_date,
        end_date=trip.end_date,
        trip_days=trip.trip_days,
    )
    assert report.trip_days == 3
    assert "仅供参考" in report.disclaimer
