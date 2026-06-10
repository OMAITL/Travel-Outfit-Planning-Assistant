"""LangGraph workflow — orchestrates all planning agents."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

import src.graph  # noqa: F401 — triggers PlanningState.model_rebuild()
from src.graph.nodes import (
    assets_node,
    inspiration_node,
    itinerary_node,
    report_node,
    stylist_node,
    trip_node,
    vision_node,
    weather_node,
)
from src.graph.report import TravelReport
from src.graph.state import ChatMessage, PlanningPhase, PlanningState

StateDict = dict[str, Any]

_COMPILED_GRAPH = None


def _parse_state(data: StateDict | PlanningState) -> PlanningState:
    if isinstance(data, PlanningState):
        return data
    return PlanningState.model_validate(data)


def _dump_state(state: PlanningState) -> StateDict:
    return state.model_dump(mode="json")


def _wrap_node(fn):
    """Adapt PlanningState nodes to LangGraph dict state."""

    def node(state: StateDict) -> StateDict:
        result = fn(_parse_state(state))
        return _dump_state(result)

    node.__name__ = fn.__name__
    return node


def _route_after_trip(state: StateDict) -> Literal["weather", "__end__"]:
    planning = _parse_state(state)
    if planning.phase == PlanningPhase.COLLECTING:
        return END
    return "weather"


def _route_after_stylist(state: StateDict) -> Literal["assets", "report"]:
    """Chat mode skips Taobao + AI image generation (assets node)."""
    planning = _parse_state(state)
    if planning.input_mode == "chat":
        return "report"
    return "assets"


def compile_workflow():
    """Build and compile the planning StateGraph."""
    builder = StateGraph(dict)
    builder.add_node("trip", _wrap_node(trip_node))
    builder.add_node("weather", _wrap_node(weather_node))
    builder.add_node("itinerary", _wrap_node(itinerary_node))
    builder.add_node("inspiration", _wrap_node(inspiration_node))
    builder.add_node("vision", _wrap_node(vision_node))
    builder.add_node("stylist", _wrap_node(stylist_node))
    builder.add_node("assets", _wrap_node(assets_node))
    builder.add_node("report", _wrap_node(report_node))

    builder.add_edge(START, "trip")
    builder.add_conditional_edges("trip", _route_after_trip, {"weather": "weather", END: END})
    builder.add_edge("weather", "itinerary")
    builder.add_edge("itinerary", "inspiration")
    builder.add_edge("inspiration", "vision")
    builder.add_edge("vision", "stylist")
    builder.add_conditional_edges(
        "stylist",
        _route_after_stylist,
        {"assets": "assets", "report": "report"},
    )
    builder.add_edge("assets", "report")
    builder.add_edge("report", END)

    return builder.compile()


def get_compiled_graph():
    """Return a cached compiled graph instance."""
    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None:
        _COMPILED_GRAPH = compile_workflow()
    return _COMPILED_GRAPH


def run_planning(
    user_message: str,
    *,
    state: PlanningState | None = None,
) -> PlanningState:
    """
    Run one planning turn: append the user message and invoke the graph.

    When trip info is incomplete the graph stops after ``trip`` with
    ``phase=COLLECTING``; pass the returned state back on the next turn.
    """
    text = user_message.strip()
    if not text:
        msg = "user_message must not be empty"
        raise ValueError(msg)

    current = state or PlanningState()
    current = current.model_copy(
        update={"messages": [*current.messages, ChatMessage(role="user", content=text)]}
    )

    graph = get_compiled_graph()
    result = graph.invoke(_dump_state(current))
    return _parse_state(result)


def run_planning_report(
    user_message: str,
    *,
    state: PlanningState | None = None,
) -> TravelReport | None:
    """Convenience wrapper that returns ``TravelReport`` when planning completes."""
    final = run_planning(user_message, state=state)
    return final.report


def _cli_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the travel outfit planning workflow")
    parser.add_argument(
        "--demo",
        metavar="MESSAGE",
        help='User message, e.g. "7月10-12日去大理，休闲风"',
    )
    parser.add_argument(
        "--mock-fixture",
        action="store_true",
        help="Start from tests/fixtures/planning_state.json (skips trip LLM if complete)",
    )
    parser.add_argument("--json", action="store_true", help="Print full state as JSON")
    args = parser.parse_args(argv)

    if args.mock_fixture:
        fixture_path = (
            __import__("pathlib").Path(__file__).resolve().parents[2]
            / "tests"
            / "fixtures"
            / "planning_state.json"
        )
        initial = PlanningState.model_validate(json.loads(fixture_path.read_text(encoding="utf-8")))
        initial = initial.model_copy(
            update={
                "phase": PlanningPhase.PLANNING,
                "look_images": [],
                "products": [],
                "report": None,
            }
        )
        message = args.demo or "继续规划穿搭"
        result = run_planning(message, state=initial)
    elif args.demo:
        result = run_planning(args.demo)
    else:
        parser.print_help()
        return 1

    if args.json:
        print(json.dumps(_dump_state(result), ensure_ascii=False, indent=2))
    elif result.report:
        print(result.report.summary or "")
        print(f"\n{result.report.destination} · {result.report.trip_days} 天")
        for card in result.report.daily_cards:
            outfit = card.outfit.outfit_summary if card.outfit else "-"
            print(f"\n{card.date}: {outfit}")
            print(f"  图: {card.look_image_url or '无'}")
            print(f"  商品: {len(card.products)}")
    elif result.phase == PlanningPhase.COLLECTING:
        print(result.messages[-1].content)
    else:
        print("Planning finished without a report.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(_cli_main())
