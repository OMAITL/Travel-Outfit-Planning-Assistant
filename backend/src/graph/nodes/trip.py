"""Trip Agent node — parse user message into TripContext."""

from __future__ import annotations

from datetime import date

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, field_validator

from src.graph.state import ChatMessage, PlanningPhase, PlanningState, TripContext, TripPreferences
from src.services.chat_intent import (
    ChatIntentDraft,
    apply_message_quick_replies,
    build_intent_draft,
    finalize_trip_intent,
    merge_extraction_with_draft,
    merge_quick_replies,
    resolve_awaiting_spot_pick,
)
from src.services.llm import get_chat_model, invoke_structured, load_prompt


class TripExtraction(BaseModel):
    destination: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    activities: list[str] = Field(default_factory=list)
    scene_type: str | None = None
    style_tendency: str = ""
    climate_hint: str = ""
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
    avoid_items_acknowledged: bool = False
    spot_names: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    is_complete: bool = False
    follow_up_question: str | None = None
    follow_up_field: str | None = None
    follow_up_options: list[str] = Field(default_factory=list)

    @field_validator(
        "activities",
        "avoid_items",
        "missing_fields",
        "follow_up_options",
        "spot_names",
        mode="before",
    )
    @classmethod
    def _coerce_null_lists(cls, value: list[str] | None) -> list[str]:
        """LLM often returns null instead of [] — must not crash the graph."""
        return value if value is not None else []

    @field_validator("style_tendency", "climate_hint", mode="before")
    @classmethod
    def _coerce_null_str(cls, value: str | None) -> str:
        return value if value is not None else ""

    @field_validator("style", mode="before")
    @classmethod
    def _coerce_null_style(cls, value: str | None) -> str:
        return value if value is not None else "休闲"

    @field_validator("party_size", mode="before")
    @classmethod
    def _coerce_null_party_size(cls, value: int | None) -> int:
        return value if value is not None else 1

    @field_validator("avoid_items_acknowledged", "is_complete", mode="before")
    @classmethod
    def _coerce_null_bool(cls, value: bool | None) -> bool:
        return value if value is not None else False


def _conversation_text(state: PlanningState) -> str:
    if not state.messages:
        return ""
    lines = [f"{msg.role}: {msg.content}" for msg in state.messages]
    return "\n".join(lines)


def _last_user_message(state: PlanningState) -> str:
    for msg in reversed(state.messages):
        if msg.role == "user":
            return msg.content.strip()
    return ""


def trip_node(state: PlanningState, *, llm=None) -> PlanningState:
    if state.trip is not None and state.trip.is_complete:
        return state.model_copy(update={"phase": PlanningPhase.PLANNING}).append_trace(
            "Trip",
            f"TripContext ready: {state.trip.destination} ({state.trip.trip_days} days)",
        )

    state = state.append_trace("Trip", "parsing outfit-first trip intent")
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

    draft: ChatIntentDraft | None = None
    if state.chat_intent:
        draft = ChatIntentDraft.model_validate(state.chat_intent)

    merged = merge_extraction_with_draft(
        destination=extraction.destination,
        start_date=extraction.start_date,
        end_date=extraction.end_date,
        scene_type=extraction.scene_type,
        style_tendency=extraction.style_tendency,
        climate_hint=extraction.climate_hint,
        gender=extraction.gender,
        spot_names=extraction.spot_names,
        budget_per_item=extraction.budget_per_item,
        budget_total=extraction.budget_total,
        height_cm=extraction.height_cm,
        weight_kg=extraction.weight_kg,
        body_type=extraction.body_type,
        skin_tone=extraction.skin_tone,
        avoid_items=extraction.avoid_items,
        avoid_items_acknowledged=extraction.avoid_items_acknowledged,
        activities=extraction.activities,
        style=extraction.style,
        draft=draft,
    )

    last_user = _last_user_message(state)
    quick = apply_message_quick_replies(
        last_user,
        destination=merged.get("destination"),  # type: ignore[arg-type]
    )
    awaiting_spot_pick = resolve_awaiting_spot_pick(quick=quick, draft=draft)
    merged = merge_quick_replies(merged, quick)

    intent = finalize_trip_intent(
        destination=merged["destination"],  # type: ignore[arg-type]
        start_date=merged["start_date"],  # type: ignore[arg-type]
        end_date=merged["end_date"],  # type: ignore[arg-type]
        scene_type=merged["scene_type"],  # type: ignore[arg-type]
        style_tendency=merged["style_tendency"],  # type: ignore[arg-type]
        climate_hint=merged["climate_hint"],  # type: ignore[arg-type]
        gender=merged["gender"],  # type: ignore[arg-type]
        spot_names=merged["spot_names"],  # type: ignore[arg-type]
        budget_per_item=merged["budget_per_item"],  # type: ignore[arg-type]
        budget_total=merged["budget_total"],  # type: ignore[arg-type]
        height_cm=merged["height_cm"],  # type: ignore[arg-type]
        weight_kg=merged["weight_kg"],  # type: ignore[arg-type]
        body_type=merged["body_type"],  # type: ignore[arg-type]
        skin_tone=merged["skin_tone"],  # type: ignore[arg-type]
        avoid_items=merged["avoid_items"],  # type: ignore[arg-type]
        avoid_items_acknowledged=merged["avoid_items_acknowledged"],  # type: ignore[arg-type]
        activities=merged["activities"],  # type: ignore[arg-type]
        style=merged["style"],  # type: ignore[arg-type]
        is_complete=extraction.is_complete,
        follow_up_question=extraction.follow_up_question,
        follow_up_field=extraction.follow_up_field,
        follow_up_options=extraction.follow_up_options,
        require_budget=state.input_mode != "chat",
        awaiting_spot_pick=awaiting_spot_pick,
    )

    if not intent.is_complete:
        question = intent.follow_up_question or "再补充一点行程信息吧～"
        messages = [
            *state.messages,
            ChatMessage(
                role="assistant",
                content=question,
                options=intent.follow_up_options,
            ),
        ]
        draft = build_intent_draft(intent)
        trace_msg = (
            f"awaiting {intent.follow_up_field or 'input'}: "
            f"missing={','.join(intent.missing_fields) or 'none'}"
        )
        return state.model_copy(
            update={
                "messages": messages,
                "chat_intent": draft.model_dump(mode="json"),
                "phase": PlanningPhase.COLLECTING,
            }
        ).append_trace("Trip", trace_msg, level="warning")

    trip = TripContext(
        destination=intent.destination or "",
        start_date=intent.start_date,  # type: ignore[arg-type]
        end_date=intent.end_date,  # type: ignore[arg-type]
        preferences=TripPreferences(
            activities=intent.activities,
            scene_type=intent.scene_type,
            gender=intent.gender,
            style=intent.style,
            spot_names=intent.spot_names,
            budget_per_item=intent.budget_per_item,
            budget_total=intent.budget_total,
            party_size=extraction.party_size,
            height_cm=intent.height_cm,
            weight_kg=intent.weight_kg,
            body_type=intent.body_type,
            skin_tone=intent.skin_tone,
            avoid_items=intent.avoid_items,
        ),
        is_complete=True,
    ).mark_complete()

    return state.model_copy(
        update={
            "trip": trip,
            "chat_intent": None,
            "phase": PlanningPhase.PLANNING,
        }
    ).append_trace(
        "Trip",
        f"TripContext ready: {trip.destination} ({trip.trip_days} days, scene={intent.scene_type})",
    )
