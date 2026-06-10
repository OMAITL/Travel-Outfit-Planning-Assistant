import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import src.graph  # noqa: F401 — triggers PlanningState.model_rebuild()
from src.graph.nodes.image import image_node
from src.graph.nodes.report import report_node
from src.graph.nodes.shopping import shopping_node
from src.graph.nodes.stylist import StylistOutput, stylist_node
from src.graph.nodes.trip import TripExtraction, trip_node
from src.graph.nodes.weather import weather_node
from src.graph.state import (
    ChatMessage,
    DailyOutfit,
    DailyWeather,
    DayItinerary,
    PlanningPhase,
    PlanningState,
    TripContext,
    WeatherCondition,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "planning_state.json"


def _load_fixture_state() -> PlanningState:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return PlanningState.model_validate(payload)


def _mock_llm(return_value):
    llm = MagicMock()
    structured = MagicMock()
    structured.invoke.return_value = return_value
    llm.with_structured_output.return_value = structured
    return llm


def test_trip_extraction_coerces_null_avoid_items() -> None:
    model = TripExtraction.model_validate(
        {
            "is_complete": True,
            "destination": "大理",
            "start_date": "2026-06-05",
            "end_date": "2026-06-07",
            "avoid_items": None,
            "activities": None,
        }
    )
    assert model.avoid_items == []
    assert model.activities == []


def test_weather_node_writes_forecast() -> None:
    state = PlanningState(
        trip=TripContext(
            destination="北京",
            start_date=date(2026, 6, 3),
            end_date=date(2026, 6, 3),
            is_complete=True,
        )
    )
    forecast = [
        DailyWeather(
            date=date(2026, 6, 3),
            temp_min=17,
            temp_max=29,
            condition=WeatherCondition.SUNNY,
        )
    ]
    with patch("src.graph.nodes.weather.fetch_daily_weather", return_value=forecast):
        result = weather_node(state)

    assert len(result.weather) == 1
    assert result.phase == PlanningPhase.PLANNING
    assert any(event.agent == "Weather" for event in result.trace)


def test_shopping_node_picks_products() -> None:
    state = _load_fixture_state()
    mock_items = [
        {
            "title": "女防晒衬衫夏季",
            "pic_url": "https://img.example/1.jpg",
            "price": "49.00",
            "detail_url": "https://item.taobao.com/item.htm?id=1",
            "num_iid": "1",
        }
    ]
    with patch("src.graph.nodes.shopping.search_products", return_value=mock_items):
        result = shopping_node(state)

    assert len(result.products) >= 1
    assert result.products[0].trip_date == date(2026, 7, 10)


def test_image_node_writes_look_images() -> None:
    state = _load_fixture_state()
    with patch("src.graph.nodes.image.generate_outfit_look", return_value="https://img.example/look.png") as mock_gen:
        result = image_node(state)

    assert len(result.look_images) == 1
    assert result.look_images[0].image_url.startswith("https://")
    assert result.look_images[0].spot_name == "大理"
    mock_gen.assert_called_once()
    assert mock_gen.call_args.kwargs.get("reference_image_url") is None


def test_image_node_generates_one_image_per_spot() -> None:
    state = _load_fixture_state()
    state = state.model_copy(
        update={
            "itinerary": [
                DayItinerary(
                    date=date(2026, 7, 10),
                    spot_names=["洱海生态廊道", "大理古城"],
                )
            ]
        }
    )
    with patch("src.graph.nodes.image.generate_outfit_look", return_value="https://img.example/look.png") as mock_gen:
        result = image_node(state)

    assert len(result.look_images) == 2
    assert {look.spot_name for look in result.look_images} == {"洱海生态廊道", "大理古城"}
    assert mock_gen.call_count == 2


def test_image_node_generates_from_planned_outfit_not_xhs_reference() -> None:
    from datetime import date

    from src.graph.state import OutfitInspiration

    state = _load_fixture_state()
    state = state.model_copy(
        update={
            "outfit_inspirations": [
                OutfitInspiration(
                    trip_date=date(2026, 7, 10),
                    note_id="note-1",
                    title="洱海穿搭",
                    cover_url="https://xhs.example/outfit.jpg",
                    liked_count=5000,
                )
            ]
        }
    )
    with patch("src.graph.nodes.image.generate_outfit_look", return_value="https://img.example/look.png") as mock_gen:
        result = image_node(state)

    assert len(result.look_images) == 1
    assert mock_gen.call_args.kwargs["reference_image_url"] is None
    prompt = mock_gen.call_args.args[0]
    assert "防晒" in prompt or "shirt" in prompt.lower()


def test_image_node_skips_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SKIP_IMAGE_GENERATION", "true")
    from src.config import get_settings

    get_settings.cache_clear()
    state = _load_fixture_state()
    result = image_node(state)
    get_settings.cache_clear()

    assert result.look_images == []
    assert any("SKIP_IMAGE_GENERATION" in event.message for event in result.trace)


def test_stylist_output_wraps_bare_outfit_list() -> None:
    from datetime import date

    model = StylistOutput.model_validate(
        [
            {
                "date": "2026-06-05",
                "outfit_summary": "上装：白T | 下装：牛仔裤",
                "search_keywords": ["白T恤女"],
            }
        ]
    )
    assert len(model.outfits) == 1
    assert model.outfits[0].date == date(2026, 6, 5)


def test_stylist_output_coerces_null_payload() -> None:
    assert StylistOutput.model_validate(None).outfits == []
    assert StylistOutput.model_validate({"outfits": None}).outfits == []


def test_stylist_node_writes_outfits() -> None:
    state = _load_fixture_state()
    outfits = [
        DailyOutfit(
            date=date(2026, 7, 10),
            outfit_summary="防晒衬衫 + 阔腿裤",
            search_keywords=["女 防晒 衬衫"],
        )
    ]
    llm = _mock_llm(StylistOutput(outfits=outfits))
    result = stylist_node(state, llm=llm)

    assert len(result.outfits) == 1
    assert result.outfits[0].outfit_summary.startswith("防晒")


def test_trip_node_skips_llm_when_trip_ready() -> None:
    trip = TripContext(
        destination="大理",
        start_date=date(2026, 6, 5),
        end_date=date(2026, 6, 7),
        is_complete=True,
    ).mark_complete()
    state = PlanningState(trip=trip, phase=PlanningPhase.PLANNING)
    result = trip_node(state, llm=MagicMock())
    assert result.trip is not None
    assert result.trip.destination == "大理"
    assert result.phase == PlanningPhase.PLANNING
    assert any(event.agent == "Trip" for event in result.trace)


def test_trip_node_complete_trip() -> None:
    state = PlanningState(
        messages=[ChatMessage(role="user", content="7月1日到5日去东京观光，休闲风，预算200")]
    )
    extraction = TripExtraction(
        destination="东京",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 5),
        scene_type="度假",
        gender="女",
        spot_names=["市区闲逛"],
        budget_per_item=200.0,
        body_type="标准",
        height_cm=165.0,
        weight_kg=55.0,
        skin_tone="自然",
        avoid_items_acknowledged=True,
        is_complete=True,
    )
    result = trip_node(state, llm=_mock_llm(extraction))

    assert result.trip is not None
    assert result.trip.is_complete
    assert result.phase == PlanningPhase.PLANNING


def test_trip_node_follow_up_when_incomplete() -> None:
    state = PlanningState(messages=[ChatMessage(role="user", content="下周去云南")])
    extraction = TripExtraction(
        is_complete=False,
        follow_up_question="请告诉我具体城市和日期。",
    )
    result = trip_node(state, llm=_mock_llm(extraction))

    assert result.phase == PlanningPhase.COLLECTING
    assert result.messages[-1].role == "assistant"
    assert "城市" in result.messages[-1].content


def test_report_node_builds_travel_report() -> None:
    state = _load_fixture_state()
    with patch("src.graph.nodes.image.generate_outfit_look", return_value="https://img.example/look.png"):
        state = image_node(state)
    result = report_node(state)

    assert result.report is not None
    assert result.report.trip_days == 3
    assert len(result.report.daily_cards) == 3
    assert result.phase == PlanningPhase.DONE
