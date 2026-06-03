"""Rich outfit card with scores, items, and color palette."""

from __future__ import annotations

import streamlit as st

from app.utils.enrichment import (
    derive_outfit_scores,
    extract_color_palette,
    parse_outfit_items,
    score_stars,
)
from src.graph.state import DailyOutfit, TripPreferences


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
