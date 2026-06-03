"""Weather overview — forecast chart, trends, and travel tips."""

from __future__ import annotations

import streamlit as st

from app.utils.enrichment import weather_outfit_impact, weather_travel_tips
from src.graph.state import DailyWeather, TripContext


def _condition_text(condition) -> str:
    return condition.value if hasattr(condition, "value") else str(condition)


def render_weather_overview(
    weather: list[DailyWeather],
    trip: TripContext | None = None,
) -> None:
    """Trip-level weather panel with chart and reminders."""
    if not weather:
        st.caption("暂无天气预报数据")
        return

    st.markdown("#### 🌤 行程天气概览")

    sorted_days = sorted(weather, key=lambda d: d.date)
    chart_data = {
        "日期": [f"{d.date.month}/{d.date.day}" for d in sorted_days],
        "最高温": [d.temp_max for d in sorted_days],
        "最低温": [d.temp_min for d in sorted_days],
    }
    st.line_chart(chart_data, x="日期", y=["最高温", "最低温"], height=140)

    temp_spread = max(d.temp_max for d in sorted_days) - min(d.temp_min for d in sorted_days)
    avg_max = sum(d.temp_max for d in sorted_days) / len(sorted_days)
    rainy_days = sum(1 for d in sorted_days if "雨" in _condition_text(d.condition))

    m1, m2, m3 = st.columns(3)
    m1.metric("温差幅度", f"{temp_spread:.0f}°C")
    m2.metric("平均最高温", f"{avg_max:.0f}°C")
    m3.metric("可能降雨", f"{rainy_days} 天")

    if trip:
        st.caption(
            f"{trip.destination} · {trip.start_date} 至 {trip.end_date} · "
            f"风格 {trip.preferences.style}"
        )


def render_daily_weather_compact(
    weather: DailyWeather | None,
    outfit_summary: str | None = None,
) -> None:
    """One-line weather + optional detail expander."""
    if weather is None:
        st.caption("🌤 暂无当日天气数据")
        return

    condition = _condition_text(weather.condition)
    rain = f" · 降水{weather.rain_prob:.0f}%" if weather.rain_prob is not None else ""
    estimate = " · 季节参考" if weather.estimated else ""
    st.markdown(
        f"🌤 **{condition}** {weather.temp_min:.0f}–{weather.temp_max:.0f}°C{rain}{estimate}"
    )

    with st.expander("旅行提醒与穿搭依据", expanded=False):
        tips = weather_travel_tips(weather)
        for tip in tips:
            st.markdown(f"- {tip}")
        st.info(weather_outfit_impact(weather, outfit_summary))


def render_daily_weather_block(
    weather: DailyWeather | None, outfit_summary: str | None = None
) -> None:
    """Rich weather block for a single day card."""
    if weather is None:
        st.warning("暂无当日天气数据")
        return

    condition = _condition_text(weather.condition)
    rain = f" · 降水 {weather.rain_prob:.0f}%" if weather.rain_prob is not None else ""

    w1, w2, w3 = st.columns([2, 1, 1])
    w1.markdown(f"**{condition}** · {weather.temp_min:.0f}–{weather.temp_max:.0f}°C{rain}")
    w2.metric("最低", f"{weather.temp_min:.0f}°C")
    w3.metric("最高", f"{weather.temp_max:.0f}°C")

    tips = weather_travel_tips(weather)
    if tips:
        st.markdown("**旅行提醒**")
        for tip in tips:
            st.markdown(f"- {tip}")

    st.markdown("**天气 → 穿搭依据**")
    st.info(weather_outfit_impact(weather, outfit_summary))
