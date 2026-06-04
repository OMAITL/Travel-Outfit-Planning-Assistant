"""Single-day report card — v1 magazine tabs."""

from __future__ import annotations

import html

import streamlit as st

from app.components.look_image import render_look_image
from app.components.outfit_card import render_magazine_summary
from app.components.products_magazine import render_products_magazine
from src.graph.report import DailyReportCard
from src.graph.state import TripContext

WEEKDAY_ZH = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


def _weekday_label(card_date) -> str:
    return WEEKDAY_ZH[card_date.weekday()]


def _weather_header_line(card: DailyReportCard) -> str:
    if card.weather is None:
        return "暂无天气数据"
    condition = (
        card.weather.condition.value
        if hasattr(card.weather.condition, "value")
        else str(card.weather.condition)
    )
    rain = f" · 降水 {card.weather.rain_prob:.0f}%" if card.weather.rain_prob is not None else ""
    estimate = " · 季节参考" if card.weather.estimated else ""
    return (
        f"🌤 {condition} {card.weather.temp_min:.0f}–{card.weather.temp_max:.0f}°C"
        f"{rain}{estimate}"
    )


def render_daily_card(
    card: DailyReportCard,
    *,
    trip: TripContext | None = None,
    shopping_errors: list[str] | None = None,
    day_index: int = 0,
) -> None:
    weekday = _weekday_label(card.date)
    preferences = trip.preferences if trip else None
    destination = trip.destination if trip else ""
    budget = preferences.budget_per_item if preferences else None

    st.markdown(
        f"""
        <article class="magazine magazine-wrap-marker">
          <div class="mag-header">
            <h3>{card.date.month}月{card.date.day}日 · {weekday}</h3>
            <div class="weather-line">{html.escape(_weather_header_line(card))}</div>
          </div>
        </article>
        <span class="magazine-tabs-marker" aria-hidden="true"></span>
        """,
        unsafe_allow_html=True,
    )

    tab_summary, tab_look, tab_products = st.tabs(["概要", "AI 效果图", "推荐商品"])

    with tab_summary:
        if card.outfit:
            st.markdown('<span class="mag-body-marker" aria-hidden="true"></span>', unsafe_allow_html=True)
            col_text, col_visual = st.columns([1, 1.05], gap="small")
            with col_text:
                render_magazine_summary(
                    card.outfit,
                    preferences=preferences,
                    weather=card.weather,
                )
            with col_visual:
                if preferences and preferences.activities:
                    pills = "".join(
                        f'<span class="spot-pill{" active" if i == 0 else ""}">'
                        f"{html.escape(a)}</span>"
                        for i, a in enumerate(preferences.activities[:4])
                    )
                    st.markdown(f'<div class="spot-pills">{pills}</div>', unsafe_allow_html=True)
                render_look_image(
                    card.look_image_url,
                    destination=destination,
                    preferences=preferences,
                    on_retry=card.degraded,
                    compact=True,
                    hide_title=True,
                    frame=True,
                )
        else:
            st.warning("暂无穿搭方案")

    with tab_look:
        render_look_image(
            card.look_image_url,
            destination=destination,
            preferences=preferences,
            on_retry=card.degraded,
            compact=False,
            frame=True,
            full_height=True,
        )

    with tab_products:
        render_products_magazine(
            card.outfit,
            card.products,
            budget_per_item=budget,
            shopping_errors=shopping_errors,
            key_prefix=str(card.date),
            day_index=day_index,
        )

    if card.degraded:
        st.caption("⚠ 部分资源未获取（如 AI 图或商品），可稍后重试")
