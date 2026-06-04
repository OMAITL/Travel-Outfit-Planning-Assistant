"""Rich outfit card with scores, items, and color palette."""

from __future__ import annotations

import html

import streamlit as st

from app.utils.enrichment import (
    derive_outfit_scores,
    extract_color_palette,
    parse_outfit_items,
    score_stars,
    weather_travel_tips,
)
from src.graph.state import DailyOutfit, DailyWeather, TripPreferences


def render_outfit_card(
    outfit: DailyOutfit,
    preferences: TripPreferences | None = None,
    *,
    compact: bool = False,
) -> None:
    scores = derive_outfit_scores(outfit.outfit_summary, preferences)
    colors = extract_color_palette(outfit.outfit_summary)
    items = parse_outfit_items(outfit.outfit_summary)

    if outfit.recommendation_reason:
        st.info(f"**推荐理由** · {outfit.recommendation_reason}")

    if compact:
        score_line = (
            f"风格{score_stars(scores['style'])} · "
            f"舒适{score_stars(scores['comfort'])} · "
            f"出片{score_stars(scores['photo'])}"
        )
        color_text = " · ".join(name for name, _ in colors)
        scene = " / ".join(preferences.activities) if preferences and preferences.activities else ""
        style = preferences.style if preferences else "休闲"
        meta = f"{score_line} · 配色{color_text} · {style}"
        if scene:
            meta += f" · {scene}"
        st.caption(meta)
    else:
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"**风格匹配**  \n{score_stars(scores['style'])}")
        c2.markdown(f"**舒适度**  \n{score_stars(scores['comfort'])}")
        c3.markdown(f"**出片度**  \n{score_stars(scores['photo'])}")
        color_text = " · ".join(name for name, _ in colors)
        st.caption(f"配色：{color_text}")
        if outfit.recommendation_reason:
            st.info(f"**推荐理由** · {outfit.recommendation_reason}")

    with st.expander(f"单品清单（{len(items)} 件）", expanded=False):
        for label, text in items:
            st.markdown(
                f'<div class="outfit-item outfit-item--compact">'
                f'<span class="outfit-label">{label}</span>{text}</div>',
                unsafe_allow_html=True,
            )


def render_magazine_summary(
    outfit: DailyOutfit,
    *,
    preferences: TripPreferences | None = None,
    weather: DailyWeather | None = None,
) -> None:
    """Magazine-style left column: tips, reason, item grid, scores."""
    scores = derive_outfit_scores(outfit.outfit_summary, preferences)
    colors = extract_color_palette(outfit.outfit_summary)
    items = parse_outfit_items(outfit.outfit_summary)
    color_text = " · ".join(name for name, _ in colors)

    tips: list[str] = []
    if weather is not None:
        tips = weather_travel_tips(weather)

    tips_html = "".join(f"<li>{html.escape(tip)}</li>" for tip in tips[:4])
    if not tips_html:
        tips_html = "<li>根据当日天气灵活调整层次与材质</li>"

    reason = outfit.recommendation_reason or "方案兼顾舒适度、场景活动与拍照出片需求。"
    reason_html = html.escape(reason)

    cells_html = "".join(
        f'<div class="item-cell"><span class="lbl">{html.escape(label)}</span><br/>'
        f"{html.escape(text)}</div>"
        for label, text in items[:6]
    )

    st.markdown(
        f"""
        <div class="mag-body-text">
          <div class="section">
            <div class="section-title">旅行提醒</div>
            <ul class="tips-list">{tips_html}</ul>
          </div>
          <div class="section">
            <div class="section-title">推荐理由</div>
            <div class="reason-box">{reason_html}</div>
          </div>
          <div class="section">
            <div class="section-title">单品清单</div>
            <div class="items-grid">{cells_html}</div>
          </div>
          <div class="scores-row">
            <span>风格 {score_stars(scores["style"])}</span>
            <span>舒适 {score_stars(scores["comfort"])}</span>
            <span>出片 {score_stars(scores["photo"])}</span>
            <span>配色 {html.escape(color_text)}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
