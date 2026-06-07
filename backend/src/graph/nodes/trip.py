"""Trip Agent node — parse user message into TripContext."""

from __future__ import annotations

from datetime import date

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, field_validator

from src.graph.state import ChatMessage, PlanningPhase, PlanningState, TripContext, TripPreferences
from src.services.llm import get_chat_model, invoke_structured, load_prompt


class TripExtraction(BaseModel):
    destination: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    activities: list[str] = Field(default_factory=list)
    gender: str | None = None
    style: str = "休闲"
    budget_per_item: float | None = Field(default=None, ge=0)
    budget_total: float | None = Field(default=None, ge=0)
    party_size: int = Field(default=1, ge=1)
    height_cm: float | None = Field(default=None, ge=0)
    weight_kg: float | None = Field(default=None, ge=0)
    body_type: str | None = None
    skin_tone: str | None = None
    avoid_items: list[str] = Field(default_factory=list)
    is_complete: bool = False
    follow_up_question: str | None = None

    @field_validator("activities", "avoid_items", mode="before")
    @classmethod
    def _coerce_null_lists(cls, value: list[str] | None) -> list[str]:
        """LLM often returns null instead of [] — must not crash the graph."""
        return value if value is not None else []


def _conversation_text(state: PlanningState) -> str:
    if not state.messages:
        return ""
    lines = [f"{msg.role}: {msg.content}" for msg in state.messages]
    return "\n".join(lines)


def trip_node(state: PlanningState, *, llm=None) -> PlanningState:
    if state.trip is not None and state.trip.is_complete:
        return state.model_copy(update={"phase": PlanningPhase.PLANNING}).append_trace(
            "Trip",
            f"TripContext ready: {state.trip.destination} ({state.trip.trip_days} days)",
        )

    state = state.append_trace("Trip", "parsing trip information")
    model = llm or get_chat_model()
    system_prompt = load_prompt("trip.md").format(today=date.today().isoformat())
    user_content = _conversation_text(state) or "No user message yet."

    extraction: TripExtraction = invoke_structured(
        model,
        TripExtraction,
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content),
        ],
        retries=1,
        operation="trip_extract",
    )

    if not extraction.is_complete or not all(
        [extraction.destination, extraction.start_date, extraction.end_date]
    ):
        question = extraction.follow_up_question or "请补充目的地、出发日期和返回日期。"
        messages = [
            *state.messages,
            ChatMessage(role="assistant", content=question),
        ]
        return state.model_copy(
            update={
                "messages": messages,
                "phase": PlanningPhase.COLLECTING,
            }
        ).append_trace("Trip", "awaiting user input", level="warning")

    trip = TripContext(
        destination=extraction.destination or "",
        start_date=extraction.start_date,  # type: ignore[arg-type]
        end_date=extraction.end_date,  # type: ignore[arg-type]
        preferences=TripPreferences(
            activities=extraction.activities,
            gender=extraction.gender,
            style=extraction.style,
            budget_per_item=extraction.budget_per_item,
            budget_total=extraction.budget_total,
            party_size=extraction.party_size,
            height_cm=extraction.height_cm,
            weight_kg=extraction.weight_kg,
            body_type=extraction.body_type,
            skin_tone=extraction.skin_tone,
            avoid_items=extraction.avoid_items,
        ),
        is_complete=True,
    ).mark_complete()

    return state.model_copy(
        update={
            "trip": trip,
            "phase": PlanningPhase.PLANNING,
        }
    ).append_trace("Trip", f"TripContext ready: {trip.destination} ({trip.trip_days} days)")
