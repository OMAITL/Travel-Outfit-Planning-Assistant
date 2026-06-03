"""Single-day report card — compact 概要 / AI图 / 商品 tabs."""

from __future__ import annotations

import streamlit as st

from app.components.look_image import render_look_image
from app.components.outfit_card import render_outfit_card
from app.components.products_by_item import render_products_by_item
from app.components.weather_panel import render_daily_weather_compact
from src.graph.report import DailyReportCard
from src.graph.state import TripContext

WEEKDAY_ZH = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


def _weekday_label(card_date) -> str:
    return WEEKDAY_ZH[card_date.weekday()]


def render_daily_card(
    card: DailyReportCard,
    *,
    trip: TripContext | None = None,
    shopping_errors: list[str] | None = None,
) -> None:
    weekday = _weekday_label(card.date)
    preferences = trip.preferences if trip else None
    destination = trip.destination if trip else ""
    budget = preferences.budget_per_item if preferences else None

    st.caption(f"{card.date.month}月{card.date.day}日 · {weekday}")

    tab_summary, tab_look, tab_products = st.tabs(["概要", "AI 效果图", "推荐商品"])

    with tab_summary:
        render_daily_weather_compact(
            card.weather,
            card.outfit.outfit_summary if card.outfit else None,
        )
        if card.outfit:
            render_outfit_card(card.outfit, preferences, compact=True)
        else:
            st.warning("暂无穿搭方案")

    with tab_look:
        st.markdown('<div class="look-image-wrap look-image-wrap--tab">', unsafe_allow_html=True)
        render_look_image(
            card.look_image_url,
            destination=destination,
            preferences=preferences,
            on_retry=card.degraded,
            compact=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with tab_products:
        render_products_by_item(
            card.outfit,
            card.products,
            budget_per_item=budget,
            shopping_errors=shopping_errors,
            key_prefix=str(card.date),
            compact=True,
        )

    if card.degraded:
        st.caption("⚠ 部分资源未获取（如 AI 图或商品），可稍后重试")
