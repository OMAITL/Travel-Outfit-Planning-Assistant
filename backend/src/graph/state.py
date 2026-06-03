"""Shared Pydantic models for the planning graph."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

if TYPE_CHECKING:
    from src.graph.report import TravelReport


class WeatherCondition(StrEnum):
    SUNNY = "晴"
    CLOUDY = "多云"
    OVERCAST = "阴"
    RAINY = "雨"
    SNOWY = "雪"


class TripPreferences(BaseModel):
    activities: list[str] = Field(default_factory=list)
    gender: str | None = None
    style: str = "休闲"
    budget_per_item: float | None = Field(default=None, ge=0)
    budget_total: float | None = Field(default=None, ge=0, description="整套穿搭总预算（元）")
    party_size: int = Field(default=1, ge=1)
    height_cm: float | None = Field(default=None, ge=0)
    weight_kg: float | None = Field(default=None, ge=0)
    body_type: str | None = Field(default=None, description="苹果型 / 梨型 / H型 / 不限")
    skin_tone: str | None = None
    avoid_items: list[str] = Field(default_factory=list, description="穿搭避雷，如不穿裙子")


class TripContext(BaseModel):
    destination: str
    start_date: date
    end_date: date
    preferences: TripPreferences = Field(default_factory=TripPreferences)
    is_complete: bool = False

    @computed_field
    @property
    def trip_days(self) -> int:
        return (self.end_date - self.start_date).days + 1

    @model_validator(mode="after")
    def validate_date_range(self) -> TripContext:
        if self.end_date < self.start_date:
            msg = "end_date must not be before start_date"
            raise ValueError(msg)
        return self

    def mark_complete(self) -> TripContext:
        return self.model_copy(update={"is_complete": True})


class DailyWeather(BaseModel):
    date: date
    temp_min: float
    temp_max: float
    condition: WeatherCondition | str
    rain_prob: float | None = Field(default=None, ge=0, le=100)
    estimated: bool = Field(
        default=False,
        description="True when filled by seasonal estimate (AMap only covers ~4 days)",
    )

    @field_validator("condition", mode="before")
    @classmethod
    def normalize_condition(cls, value: object) -> WeatherCondition | str:
        if isinstance(value, WeatherCondition):
            return value
        text = str(value).strip()
        for member in WeatherCondition:
            if member.value == text:
                return member
        if "雨" in text:
            return WeatherCondition.RAINY
        if "雪" in text:
            return WeatherCondition.SNOWY
        if "晴" in text:
            return WeatherCondition.SUNNY
        if "云" in text:
            return WeatherCondition.CLOUDY
        if "阴" in text:
            return WeatherCondition.OVERCAST
        return text


class DailyOutfit(BaseModel):
    date: date
    outfit_summary: str
    search_keywords: list[str] = Field(default_factory=list)
    recommendation_reason: str = Field(
        default="",
        description="Why this outfit fits weather, body type, and user preferences",
    )

    @field_validator("search_keywords", mode="before")
    @classmethod
    def strip_keywords(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for keyword in value:
            text = " ".join(str(keyword).split())
            if text:
                cleaned.append(text)
        return cleaned


class ProductCard(BaseModel):
    title: str
    pic_url: str
    price: float
    detail_url: str
    num_iid: str | None = None
    trip_date: date | None = None


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(..., min_length=1)


class OutfitLookImage(BaseModel):
    date: date
    image_url: str
    prompt: str | None = None


class TraceEvent(BaseModel):
    agent: str
    message: str
    level: str = "info"


class PlanningPhase(StrEnum):
    COLLECTING = "collecting"
    PLANNING = "planning"
    DONE = "done"


class PlanningState(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list)
    trip: TripContext | None = None
    weather: list[DailyWeather] = Field(default_factory=list)
    outfits: list[DailyOutfit] = Field(default_factory=list)
    look_images: list[OutfitLookImage] = Field(default_factory=list)
    products: list[ProductCard] = Field(default_factory=list)
    report: TravelReport | None = None
    phase: PlanningPhase = PlanningPhase.COLLECTING
    errors: list[str] = Field(default_factory=list)
    trace: list[TraceEvent] = Field(default_factory=list)

    def append_error(self, message: str) -> PlanningState:
        return self.model_copy(update={"errors": [*self.errors, message]})

    def append_trace(
        self,
        agent: str,
        message: str,
        *,
        level: str = "info",
    ) -> PlanningState:
        event = TraceEvent(agent=agent, message=message, level=level)
        return self.model_copy(update={"trace": [*self.trace, event]})
