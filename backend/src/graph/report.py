from __future__ import annotations

from datetime import date as DateType

from pydantic import BaseModel, Field

from src.graph.state import DailyOutfit, DailyWeather, OutfitInspiration, ProductCard


class OutfitItemView(BaseModel):
    label: str
    text: str


class ProductItemGroup(BaseModel):
    """Products grouped under one outfit item (supports sub-tabs like 上装·T恤)."""

    id: str
    label: str
    item_text: str
    category: str
    products: list[ProductCard] = Field(default_factory=list, max_length=3)


class StyleReferenceView(BaseModel):
    """Xiaohongshu outfit inspiration shown in the daily report."""

    note_id: str
    title: str = ""
    cover_url: str = ""
    image_urls: list[str] = Field(default_factory=list)
    note_url: str = ""
    user_name: str | None = None
    liked_count: int | None = None
    search_keyword: str | None = None
    is_search_link: bool = Field(
        default=False,
        description="True when linking to XHS search instead of a specific note",
    )


class DailyReportCard(BaseModel):
    """Single-day slice of the final user-facing report."""

    date: DateType
    spot_names: list[str] = Field(
        default_factory=list,
        description="Scenic spots scheduled for this day",
    )
    morning: str | None = Field(default=None, description="Morning POI")
    afternoon: str | None = Field(default=None, description="Afternoon POI")
    evening: str | None = Field(default=None, description="Optional evening POI")
    plan_reason: str | None = Field(
        default=None,
        description="Planner rationale for this day's spot arrangement",
    )
    weather: DailyWeather | None = None
    outfit: DailyOutfit | None = None
    outfit_items: list[OutfitItemView] = Field(default_factory=list)
    product_groups: list[ProductItemGroup] = Field(default_factory=list)
    look_image_url: str | None = Field(
        default=None,
        description="Primary AI look image URL (first spot of the day, backward compatible)",
    )
    look_images_by_spot: dict[str, str] = Field(
        default_factory=dict,
        description="AI look image URLs keyed by scenic spot name for this day",
    )
    style_references: list[StyleReferenceView] = Field(
        default_factory=list,
        description="Xiaohongshu outfit inspiration references",
    )
    products: list[ProductCard] = Field(
        default_factory=list,
        max_length=12,
        description="Up to 3 matched products per category (top/bottom/shoes/acc) per day",
    )
    travel_tips: list[str] = Field(
        default_factory=list,
        description="Weather-based travel reminders for this day",
    )
    degraded: bool = Field(
        default=False,
        description="True when some assets (image/products) failed and were degraded",
    )


class TravelReport(BaseModel):
    """Top-level report returned to the UI layer."""

    destination: str
    start_date: DateType
    end_date: DateType
    trip_days: int
    daily_cards: list[DailyReportCard] = Field(default_factory=list)
    summary: str | None = None
    disclaimer: str = Field(
        default="穿搭与商品推荐仅供参考；AI 搭配图为示意；价格与库存以淘宝页面为准。",
    )
