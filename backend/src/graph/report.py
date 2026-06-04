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


class DailyReportCard(BaseModel):
    """Single-day slice of the final user-facing report."""

    date: DateType
    spot_names: list[str] = Field(
        default_factory=list,
        description="Scenic spots scheduled for this day",
    )
    weather: DailyWeather | None = None
    outfit: DailyOutfit | None = None
    outfit_items: list[OutfitItemView] = Field(default_factory=list)
    product_groups: list[ProductItemGroup] = Field(default_factory=list)
    look_image_url: str | None = Field(
        default=None,
        description="AI-generated outfit look image URL (Phase 4+)",
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
