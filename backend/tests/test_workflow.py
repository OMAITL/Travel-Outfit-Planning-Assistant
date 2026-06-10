import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

import src.graph  # noqa: F401 — triggers PlanningState.model_rebuild()
from src.graph.nodes.stylist import StylistOutput
from src.graph.nodes.trip import TripExtraction
from src.graph.report import TravelReport
from src.graph.state import (
    DailyOutfit,
    DailyWeather,
    PlanningPhase,
    PlanningState,
    WeatherCondition,
)
from src.graph.workflow import (
    _route_after_stylist,
    _route_after_trip,
    compile_workflow,
    get_compiled_graph,
    run_planning,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "planning_state.json"


def _load_fixture_state() -> PlanningState:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return PlanningState.model_validate(payload)


def test_route_after_trip_collecting_ends() -> None:
    state = PlanningState(phase=PlanningPhase.COLLECTING).model_dump(mode="json")
    assert _route_after_trip(state) == "__end__"


def test_route_after_trip_planning_continues() -> None:
    state = PlanningState(phase=PlanningPhase.PLANNING).model_dump(mode="json")
    assert _route_after_trip(state) == "weather"


def test_route_after_stylist_chat_skips_assets() -> None:
    state = PlanningState(input_mode="chat").model_dump(mode="json")
    assert _route_after_stylist(state) == "report"


def test_route_after_stylist_form_uses_assets() -> None:
    state = PlanningState(input_mode="form").model_dump(mode="json")
    assert _route_after_stylist(state) == "assets"


def test_run_planning_stops_when_collecting() -> None:
    extraction = TripExtraction(
        destination="大理",
        is_complete=False,
        follow_up_question="你这次更偏向哪种穿搭场景？",
        follow_up_field="scene_type",
        follow_up_options=["出片拍照", "舒适休闲", "混合风格"],
    )
    with patch("src.graph.nodes.trip.invoke_structured", return_value=extraction):
        result = run_planning("去大理怎么玩")

    assert result.phase == PlanningPhase.COLLECTING
    assert result.messages[-1].role == "assistant"
    assert "什么时候" in result.messages[-1].content or "出发" in result.messages[-1].content
    assert result.chat_intent is not None
    assert result.chat_intent.get("destination") == "大理"
    assert result.report is None


def test_full_workflow_with_mocked_nodes() -> None:
    fixture = _load_fixture_state()
    trip = fixture.trip
    assert trip is not None

    extraction = TripExtraction(
        destination=trip.destination,
        start_date=trip.start_date,
        end_date=trip.end_date,
        scene_type="度假",
        is_complete=True,
    )
    forecast = [
        DailyWeather(
            date=date(2026, 7, 10),
            temp_min=18,
            temp_max=26,
            condition=WeatherCondition.SUNNY,
        )
    ]
    outfits = [
        DailyOutfit(
            date=date(2026, 7, 10),
            outfit_summary="防晒衬衫 + 阔腿裤",
            search_keywords=["女 防晒 衬衫"],
        )
    ]

    with (
        patch("src.graph.nodes.trip.invoke_structured", return_value=extraction),
        patch("src.graph.nodes.weather.fetch_daily_weather", return_value=forecast),
        patch(
            "src.graph.nodes.stylist.invoke_structured", return_value=StylistOutput(outfits=outfits)
        ),
        patch(
            "src.graph.nodes.image.generate_outfit_look",
            return_value="https://img.example/look.png",
        ),
        patch(
            "src.graph.nodes.shopping.search_products",
            return_value=[
                {
                    "title": "防晒衬衫",
                    "pic_url": "https://img.example/1.jpg",
                    "price": "49.00",
                    "detail_url": "https://item.taobao.com/item.htm?id=1",
                    "num_iid": "1",
                }
            ],
        ),
    ):
        result = run_planning("7月10日到12日去大理")

    assert result.phase == PlanningPhase.DONE
    assert result.report is not None
    assert isinstance(result.report, TravelReport)
    assert len(result.report.daily_cards) >= 1
    assert any(event.agent == "Assets" for event in result.trace)


def test_chat_mode_skips_assets() -> None:
    fixture = _load_fixture_state()
    trip = fixture.trip
    assert trip is not None

    extraction = TripExtraction(
        destination=trip.destination,
        start_date=trip.start_date,
        end_date=trip.end_date,
        scene_type="度假",
        is_complete=True,
    )
    forecast = [
        DailyWeather(
            date=date(2026, 7, 10),
            temp_min=18,
            temp_max=26,
            condition=WeatherCondition.SUNNY,
        )
    ]
    outfits = [
        DailyOutfit(
            date=date(2026, 7, 10),
            outfit_summary="防晒衬衫 + 阔腿裤",
            search_keywords=["女 防晒 衬衫"],
        )
    ]
    initial = PlanningState(input_mode="chat", phase=PlanningPhase.PLANNING, trip=trip)

    import src.graph.workflow as wf

    def _noop_node(state: PlanningState) -> PlanningState:
        return state

    wf._COMPILED_GRAPH = None
    with (
        patch("src.graph.nodes.trip.invoke_structured", return_value=extraction),
        patch("src.graph.nodes.weather.fetch_daily_weather", return_value=forecast),
        patch(
            "src.graph.nodes.stylist.invoke_structured", return_value=StylistOutput(outfits=outfits)
        ),
        patch("src.graph.workflow.inspiration_node", _noop_node),
        patch("src.graph.workflow.vision_node", _noop_node),
        patch("src.graph.nodes.image.generate_outfit_look") as mock_image,
        patch("src.graph.nodes.shopping.search_products") as mock_shop,
    ):
        result = run_planning("7月10日到12日去大理", state=initial)
    wf._COMPILED_GRAPH = None

    assert result.phase == PlanningPhase.DONE
    assert result.report is not None
    assert not any(event.agent == "Assets" for event in result.trace)
    mock_image.assert_not_called()
    mock_shop.assert_not_called()


def test_compile_workflow_is_cached() -> None:
    assert get_compiled_graph() is get_compiled_graph()


def test_graph_structure_has_expected_nodes() -> None:
    graph = compile_workflow()
    node_names = set(graph.get_graph().nodes)
    assert {
        "trip",
        "weather",
        "inspiration",
        "vision",
        "stylist",
        "assets",
        "report",
    }.issubset(node_names)
