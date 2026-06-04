"""API request/response models."""

from __future__ import annotations

from datetime import date

from typing import Literal

from pydantic import BaseModel, Field

from src.graph.state import PlanningState


class BudgetByCategoryIn(BaseModel):
    top: float = Field(ge=0)
    bottom: float = Field(ge=0)
    shoes: float = Field(ge=0)
    acc: float = Field(ge=0)


class TripFormIn(BaseModel):
    destination: str
    start_date: date
    end_date: date
    gender: str = "女"
    styles: list[str] = Field(default_factory=lambda: ["休闲"])
    activities: list[str] = Field(default_factory=lambda: ["拍照", "逛街"])
    spot_names: list[str] = Field(default_factory=list)
    plan_mode: Literal["auto", "manual"] = "auto"
    daily_spot_names: list[list[str]] = Field(
        default_factory=list,
        description="Manual mode: spot names per day, aligned with trip dates",
    )
    budget_per_item: float | None = None
    budget_total: float | None = None
    budget_by_category: BudgetByCategoryIn | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    body_type: str | None = None
    skin_tone: str | None = None
    avoid_items: list[str] = Field(default_factory=list)


class PlanRequest(BaseModel):
    """Either free-text message or structured trip form (or both)."""

    message: str | None = None
    trip: TripFormIn | None = None
    state: dict | None = Field(
        default=None,
        description="Previous PlanningState JSON for multi-turn chat",
    )


class PlanResponse(BaseModel):
    state: PlanningState


class SpotOut(BaseModel):
    id: str
    emoji: str
    name: str
    tag: str


class CityOut(BaseModel):
    key: str
    name: str
    spots: list[SpotOut]
    default_spot_ids: list[str]


class CatalogResponse(BaseModel):
    cities: list[CityOut]
