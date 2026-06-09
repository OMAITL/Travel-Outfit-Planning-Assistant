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


class BudgetByCategory(BaseModel):
    """Per-category item budgets from the Vue trip form (CNY)."""

    top: float = Field(default=0, ge=0)
    bottom: float = Field(default=0, ge=0)
    shoes: float = Field(default=0, ge=0)
    acc: float = Field(default=0, ge=0)

    @property
    def total(self) -> float:
        return self.top + self.bottom + self.shoes + self.acc

    @property
    def max_item(self) -> float:
        return max(self.top, self.bottom, self.shoes, self.acc)


class TripPreferences(BaseModel):
    activities: list[str] = Field(default_factory=list)
    gender: str | None = None
    style: str = "休闲"
    spot_names: list[str] = Field(default_factory=list, description="User-selected scenic spots")
    plan_mode: Literal["auto", "manual"] = Field(
        default="auto",
        description="auto = round-robin spot allocation; manual = user picks per day",
    )
    budget_per_item: float | None = Field(default=None, ge=0)
    budget_total: float | None = Field(default=None, ge=0, description="整套穿搭总预算（元）")
    budget_by_category: BudgetByCategory | None = None
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
    def strip_keywords(cls, value: list[str] | None) -> list[str]:
        if value is None:
            return []
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
    category: Literal["top", "bottom", "shoes", "acc"] | None = Field(
        default=None,
        description="Item category for UI tabs",
    )
    item_label: str | None = Field(default=None, description="Outfit item label, e.g. 上装")
    item_text: str | None = Field(default=None, description="Parsed outfit item description")
    within_budget: bool = Field(default=True)
    size_hint: str | None = None


class DayItinerary(BaseModel):
    """Spots scheduled for a single trip day."""

    date: date
    spot_names: list[str] = Field(default_factory=list)
    morning: str | None = Field(default=None, description="Morning POI")
    afternoon: str | None = Field(default=None, description="Afternoon POI")
    evening: str | None = Field(default=None, description="Optional evening POI")
    plan_reason: str | None = Field(
        default=None,
        description="AI/rule planner rationale for this day's arrangement",
    )


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(..., min_length=1)


class OutfitLookImage(BaseModel):
    date: date
    image_url: str
    spot_name: str | None = Field(
        default=None,
        description="Scenic spot used as the image background; None when only destination is used",
    )
    prompt: str | None = None


class OutfitInspiration(BaseModel):
    """Xiaohongshu outfit reference from Just One API."""

    trip_date: date
    note_id: str
    title: str = ""
    desc: str = ""
    cover_url: str = ""
    image_urls: list[str] = Field(default_factory=list)
    note_url: str = ""
    user_name: str | None = None
    liked_count: int | None = None
    search_keyword: str | None = None
    is_search_link: bool = Field(
        default=False,
        description="True when this row is a Xiaohongshu search deep-link, not a fetched note",
    )


class NoteOutfitAnalysis(BaseModel):
    """Structured outfit elements extracted from a Xiaohongshu note."""

    note_id: str
    is_outfit: bool = Field(
        default=True,
        description="True only when the note actually shows a wearable outfit (not a guide/pose note)",
    )
    style: str = ""
    top: str = ""
    bottom: str = ""
    shoes: str = ""
    bag: str = ""
    accessories: str = ""
    color_palette: str = ""
    scene_vibe: str = ""
    photo_style: str = ""
    image_prompt_en: str = ""


class XhsStyleProfile(BaseModel):
    """Aggregated outfit patterns from top-liked Xiaohongshu notes."""

    top_style: str = ""
    common_tops: list[str] = Field(default_factory=list)
    common_bottoms: list[str] = Field(default_factory=list)
    common_outerwear: list[str] = Field(default_factory=list)
    common_shoes: list[str] = Field(default_factory=list)
    common_accessories: list[str] = Field(default_factory=list)
    recommended_colors: list[str] = Field(default_factory=list)
    common_silhouettes: list[str] = Field(default_factory=list)


class DayOutfitTrend(BaseModel):
    """Aggregated popular outfit trends for one trip day from XHS references."""

    date: date
    dominant_style: str = ""
    top_picks: list[str] = Field(default_factory=list)
    bottom_picks: list[str] = Field(default_factory=list)
    shoes_picks: list[str] = Field(default_factory=list)
    bag_picks: list[str] = Field(default_factory=list)
    acc_picks: list[str] = Field(default_factory=list)
    color_palette: str = ""
    scene_vibe: str = ""
    photo_style: str = ""
    editorial_prompt_en: str = ""
    style_profile: XhsStyleProfile | None = None
    note_analyses: list[NoteOutfitAnalysis] = Field(default_factory=list)


class TraceEvent(BaseModel):
    agent: str
    message: str
    level: str = "info"


class XhsQueryDebugEntry(BaseModel):
    """Outfit Query Compiler debug row (one scenic spot on one trip day)."""

    trip_date: date
    spot: str
    profile: dict = Field(default_factory=dict)
    final_query: str = ""
    base_tokens: list[dict] = Field(default_factory=list)
    expanded_queries: list[str] = Field(default_factory=list)
    compile_source: str = "rule"
    filtered_avoid: int = 0
    filtered_non_outfit: int = 0
    filtered_low_likes: int = 0
    notes_kept: int = 0


class PlanningPhase(StrEnum):
    COLLECTING = "collecting"
    PLANNING = "planning"
    DONE = "done"


class PlanningState(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list)
    trip: TripContext | None = None
    itinerary: list[DayItinerary] = Field(
        default_factory=list,
        description="Per-day scenic spot allocation for the trip",
    )
    weather: list[DailyWeather] = Field(default_factory=list)
    outfits: list[DailyOutfit] = Field(default_factory=list)
    look_images: list[OutfitLookImage] = Field(default_factory=list)
    outfit_inspirations: list[OutfitInspiration] = Field(default_factory=list)
    outfit_trends: list[DayOutfitTrend] = Field(default_factory=list)
    xhs_query_debug: list[XhsQueryDebugEntry] = Field(
        default_factory=list,
        description="Outfit Query Compiler debug rows for XHS search",
    )
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
