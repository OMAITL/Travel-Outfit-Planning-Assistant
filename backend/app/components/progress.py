"""Progress step bar mapped from PlanningState trace."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import streamlit as st

from src.graph.state import PlanningPhase, PlanningState

STEP_LABELS = (
    "行程信息",
    "天气查询",
    "穿搭规划",
    "搭配示意图",
    "商品匹配",
    "生成报告",
)


class StepStatus(StrEnum):
    DONE = "done"
    ACTIVE = "active"
    PENDING = "pending"
    WARNING = "warning"


@dataclass(frozen=True)
class StepView:
    label: str
    status: StepStatus


def _trace_agents(state: PlanningState) -> set[str]:
    return {event.agent for event in state.trace}


def _has_warning_for_agents(state: PlanningState, agents: set[str]) -> bool:
    return any(
        event.agent in agents and event.level in ("warning", "error") for event in state.trace
    )


def compute_steps(state: PlanningState | None, *, is_planning: bool = False) -> list[StepView]:
    """Derive the six PRD progress steps from backend state."""
    if state is None:
        return [StepView(label=label, status=StepStatus.PENDING) for label in STEP_LABELS]

    agents = _trace_agents(state)
    trip_done = state.trip is not None and state.trip.is_complete
    weather_done = bool(state.weather) or (
        "Weather" in agents and not _has_warning_for_agents(state, {"Weather"})
    )
    weather_warn = "Weather" in agents and _has_warning_for_agents(state, {"Weather"})
    stylist_done = bool(state.outfits)
    image_done = bool(state.look_images) or _has_warning_for_agents(state, {"Image", "Assets"})
    shopping_done = bool(state.products) or _has_warning_for_agents(state, {"Shopping", "Assets"})
    report_done = state.report is not None

    raw_statuses: list[tuple[bool, bool]] = [
        (trip_done, False),
        (weather_done, weather_warn and not weather_done),
        (stylist_done, False),
        (image_done, state.errors and not state.look_images),
        (shopping_done, state.errors and not state.products),
        (report_done, False),
    ]

    steps: list[StepView] = []
    active_assigned = False
    for label, (done, warn) in zip(STEP_LABELS, raw_statuses, strict=True):
        if done:
            status = StepStatus.WARNING if warn else StepStatus.DONE
        elif is_planning and not active_assigned:
            status = StepStatus.ACTIVE
            active_assigned = True
        elif state.phase == PlanningPhase.COLLECTING and label == STEP_LABELS[0]:
            status = StepStatus.ACTIVE
            active_assigned = True
        else:
            status = StepStatus.PENDING
        steps.append(StepView(label=label, status=status))

    if is_planning and not active_assigned:
        for index in range(len(steps)):
            if steps[index].status == StepStatus.PENDING:
                steps[index] = StepView(label=steps[index].label, status=StepStatus.ACTIVE)
                break

    return steps


def _icon(status: StepStatus) -> str:
    return {
        StepStatus.DONE: "✓",
        StepStatus.ACTIVE: "●",
        StepStatus.PENDING: "○",
        StepStatus.WARNING: "⚠",
    }[status]


def render_progress_steps(state: PlanningState | None, *, is_planning: bool = False) -> None:
    steps = compute_steps(state, is_planning=is_planning)
    parts = [f"{_icon(step.status)} {step.label}" for step in steps]
    st.markdown(" · ".join(parts))
