"""Smoke tests for Streamlit UI components."""

from datetime import date

import src.graph  # noqa: F401
from app.components.progress import StepStatus, compute_steps
from app.utils.enrichment import (
    derive_outfit_scores,
    extract_color_palette,
    weather_outfit_impact,
    weather_travel_tips,
)
from app.utils.trip_message import build_trip_message
from src.graph.report import DailyReportCard, TravelReport
from src.graph.state import (
    DailyOutfit,
    DailyWeather,
    PlanningPhase,
    PlanningState,
    TripContext,
    WeatherCondition,
)


def test_compute_steps_empty_state() -> None:
    steps = compute_steps(None)
    assert len(steps) == 6
    assert all(step.status == StepStatus.PENDING for step in steps)


def test_compute_steps_done_report() -> None:
    state = PlanningState(
        phase=PlanningPhase.DONE,
        trip=TripContext(
            destination="大理",
            start_date=date(2026, 7, 10),
            end_date=date(2026, 7, 12),
            is_complete=True,
        ),
        weather=[
            DailyWeather(
                date=date(2026, 7, 10),
                temp_min=18,
                temp_max=26,
                condition=WeatherCondition.SUNNY,
            )
        ],
        outfits=[
            DailyOutfit(
                date=date(2026, 7, 10),
                outfit_summary="防晒衬衫",
                search_keywords=["防晒衬衫"],
            )
        ],
        report=TravelReport(
            destination="大理",
            start_date=date(2026, 7, 10),
            end_date=date(2026, 7, 12),
            trip_days=3,
            daily_cards=[
                DailyReportCard(
                    date=date(2026, 7, 10),
                    outfit=DailyOutfit(
                        date=date(2026, 7, 10),
                        outfit_summary="防晒衬衫",
                        search_keywords=["防晒衬衫"],
                    ),
                )
            ],
        ),
    )
    steps = compute_steps(state)
    assert steps[0].status == StepStatus.DONE
    assert steps[-1].status == StepStatus.DONE


def test_build_trip_message() -> None:
    message = build_trip_message(
        destination="大理",
        start_date=date(2026, 7, 10),
        end_date=date(2026, 7, 12),
        gender="女",
        styles=["休闲", "韩系"],
        activities=["拍照", "逛街"],
        budget_per_item=200,
    )
    assert "大理" in message
    assert "韩系" in message
    assert "拍照" in message
    assert "200" in message


def test_enrichment_weather_and_scores() -> None:
    weather = DailyWeather(
        date=date(2026, 7, 10),
        temp_min=18,
        temp_max=30,
        condition=WeatherCondition.SUNNY,
        rain_prob=10,
    )
    tips = weather_travel_tips(weather)
    assert any("防晒" in tip for tip in tips)

    impact = weather_outfit_impact(weather, "白色防晒衬衫")
    assert "18" in impact

    colors = extract_color_palette("白色防晒衬衫 + 藏青阔腿裤")
    assert colors[0][0] == "白"

    scores = derive_outfit_scores("白色防晒衬衫 + 白色运动鞋", None)
    assert 1 <= scores["photo"] <= 5


def test_main_module_imports() -> None:
    import app.main  # noqa: F401
