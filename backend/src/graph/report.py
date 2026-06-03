from __future__ import annotations

from datetime import date as DateType

from pydantic import BaseModel, Field

from src.graph.state import DailyOutfit, DailyWeather, ProductCard


class DailyReportCard(BaseModel):
    """Single-day slice of the final user-facing report."""

    date: DateType
    weather: DailyWeather | None = None
    outfit: DailyOutfit | None = None
    look_image_url: str | None = Field(
        default=None,
        description="AI-generated outfit look image URL (Phase 4+)",
    )
    products: list[ProductCard] = Field(
        default_factory=list,
        max_length=5,
        description="Up to 5 matched Taobao products for the day",
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
