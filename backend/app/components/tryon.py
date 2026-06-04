"""AI try-on workspace — v3 three-column layout."""

from __future__ import annotations

import html
import time
from collections.abc import Callable

import streamlit as st

from app.components.products_magazine import CATEGORY_LABELS, _group_products_by_category
from src.graph.state import PlanningState, TripContext

MODEL_AVATARS = ("👩", "👨", "🧑")
SCENE_ICONS = {
    "拍照": "📸",
    "逛街": "🛍",
    "徒步": "🥾",
    "观光": "🏛",
    "美食": "🍜",
    "海边": "🏖",
    "露营": "⛺",
}


def _init_tryon_state() -> None:
    defaults: dict[str, object] = {
        "tryon_source_mode": "virtual",
        "tryon_model_avatar": "👩",
        "tryon_day_index": 0,
        "tryon_scene_index": 0,
        "tryon_product_cat": "all",
        "tryon_selected_ids": [],
        "tryon_generated": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _scene_options(trip: TripContext | None) -> list[tuple[str, str]]:
    if trip and trip.preferences.activities:
        return [(SCENE_ICONS.get(a, "📍"), a) for a in trip.preferences.activities]
    destination = trip.destination if trip else "旅行目的地"
    return [("📍", destination)]


def _toggle_product(product_id: str) -> None:
    selected: list[str] = list(st.session_state.tryon_selected_ids)
    if product_id in selected:
        selected.remove(product_id)
    else:
        selected.append(product_id)
    st.session_state.tryon_selected_ids = selected


def render_tryon_workspace(state: PlanningState, *, on_back: Callable[[], None]) -> None:
    _init_tryon_state()

    if not state.report or not state.report.daily_cards:
        st.warning("请先生成行程报告后再使用 AI 试衣")
        if st.button("← 返回行程报告"):
            on_back()
        return

    cards = state.report.daily_cards
    trip = state.trip
    day_index = min(st.session_state.tryon_day_index, len(cards) - 1)
    card = cards[day_index]
    scenes = _scene_options(trip)
    scene_index = min(st.session_state.tryon_scene_index, len(scenes) - 1)

    summary = (
        f"{state.report.destination} · "
        f"{state.report.start_date.month}/{state.report.start_date.day}–"
        f"{state.report.end_date.month}/{state.report.end_date.day} · "
        f"用推荐商品虚拟试穿 · 景点背景联动"
    )

    st.markdown(
        f"""
        <header class="hero-fullbleed">
          <div class="hero-inner">
            <div>
              <h1>✨ AI 试衣</h1>
              <p>{html.escape(summary)}</p>
            </div>
          </div>
        </header>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="tryon-workspace">', unsafe_allow_html=True)
    st.markdown('<div class="tryon-back-btn">', unsafe_allow_html=True)
    if st.button("← 返回行程报告"):
        on_back()
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<span class="tryon-grid-marker" aria-hidden="true"></span>', unsafe_allow_html=True)
    col_person, col_pool, col_preview = st.columns(3)

    prefs = trip.preferences if trip else None
    height_default = int(prefs.height_cm) if prefs and prefs.height_cm else 169
    weight_default = int(prefs.weight_kg) if prefs and prefs.weight_kg else 63

    with col_person:
        st.markdown('<span class="tryon-col-1" aria-hidden="true"></span>', unsafe_allow_html=True)
        st.markdown('<div class="panel-title">① 试穿人物</div>', unsafe_allow_html=True)

        st.markdown('<div class="source-mode-row">', unsafe_allow_html=True)
        s1, s2 = st.columns(2)
        virtual = st.session_state.tryon_source_mode == "virtual"
        with s1:
            if st.button(
                "🧍 虚拟模特\n无需真人照",
                key="tryon_mode_virtual",
                type="primary" if virtual else "secondary",
                use_container_width=True,
            ):
                st.session_state.tryon_source_mode = "virtual"
                st.rerun()
        with s2:
            if st.button(
                "📷 上传照片\n真人试穿",
                key="tryon_mode_photo",
                type="primary" if not virtual else "secondary",
                use_container_width=True,
            ):
                st.session_state.tryon_source_mode = "photo"
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        if virtual:
            st.markdown('<div class="panel-title">模特形象</div>', unsafe_allow_html=True)
            st.markdown('<div class="model-pick-row">', unsafe_allow_html=True)
            av_cols = st.columns(3)
            for av_col, avatar in zip(av_cols, MODEL_AVATARS, strict=True):
                with av_col:
                    if st.button(
                        avatar,
                        key=f"tryon_av_{avatar}",
                        type="primary"
                        if st.session_state.tryon_model_avatar == avatar
                        else "secondary",
                        use_container_width=True,
                    ):
                        st.session_state.tryon_model_avatar = avatar
                        st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
            st.markdown('<p class="dim-note">🔒 无需上传真人照片，使用虚拟模特试穿</p>', unsafe_allow_html=True)
        else:
            st.markdown(
                """
                <div class="upload-zone">
                  <div style="font-size:1.8rem">📷</div>
                  <p style="font-size:0.78rem;color:var(--muted)">点击上传全身照</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.file_uploader("上传全身照", type=["jpg", "jpeg", "png"], key="tryon_photo", label_visibility="collapsed")
            st.markdown(
                '<p class="privacy-tip">照片仅用于本次试穿；可随时切回「虚拟模特」</p>',
                unsafe_allow_html=True,
            )

        st.markdown('<div class="panel-title">② 身材数据</div>', unsafe_allow_html=True)
        st.markdown('<div class="dim-block-wrap">', unsafe_allow_html=True)
        st.markdown(
            '<p class="size-stack-hint">填写量体数据，提高 AI 试穿精度（均可选）</p>',
            unsafe_allow_html=True,
        )
        h_col, w_col = st.columns(2)
        with h_col:
            body_height = st.number_input("身高 (cm)", min_value=0, max_value=230, value=height_default)
        with w_col:
            body_weight = st.number_input("体重 (kg)", min_value=0, max_value=200, value=weight_default)
        with st.expander("上身尺码"):
            c1, c2 = st.columns(2)
            c1.number_input("肩宽 (cm)", min_value=0.0, step=0.5, key="tryon_shoulder")
            c2.number_input("上胸围 (cm)", min_value=0.0, step=0.5, key="tryon_chest")
        with st.expander("下身尺码"):
            c1, c2 = st.columns(2)
            c1.number_input("腰围 (cm)", min_value=0.0, step=0.5, key="tryon_waist")
            c2.number_input("臀围 (cm)", min_value=0.0, step=0.5, key="tryon_hip")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="panel-title">③ 日期与景点背景</div>', unsafe_allow_html=True)
        st.markdown('<div class="dim-block-wrap spot-block">', unsafe_allow_html=True)
        st.markdown(
            '<p class="size-stack-hint">选择试穿日期与 AI 合成背景景点</p>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="day-chips-row">', unsafe_allow_html=True)
        day_cols = st.columns(min(len(cards), 5))
        for index, (dcol, day_card) in enumerate(zip(day_cols, cards, strict=False)):
            with dcol:
                label = f"{day_card.date.month}/{day_card.date.day}"
                if st.button(
                    label,
                    key=f"tryon_day_{index}",
                    type="primary" if index == day_index else "secondary",
                    use_container_width=True,
                ):
                    st.session_state.tryon_day_index = index
                    st.session_state.tryon_generated = False
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="spot-list-btns">', unsafe_allow_html=True)
        for s_index, (icon, name) in enumerate(scenes):
            if st.button(
                f"{icon} {name}",
                key=f"tryon_scene_{s_index}",
                type="primary" if s_index == scene_index else "secondary",
                use_container_width=True,
            ):
                st.session_state.tryon_scene_index = s_index
                st.rerun()
        st.markdown("</div></div>", unsafe_allow_html=True)

    buckets = _group_products_by_category(card.outfit, card.products)
    all_products = buckets["all"]
    product_ids = [p.num_iid or p.detail_url for p in all_products]

    with col_pool:
        st.markdown('<span class="tryon-col-2" aria-hidden="true"></span>', unsafe_allow_html=True)
        st.markdown('<div class="panel-title">④ 推荐商品池</div>', unsafe_allow_html=True)
        st.markdown('<div class="tryon-fill-btn">', unsafe_allow_html=True)
        if st.button("↻ 一键填充今日推荐", use_container_width=True, key="tryon_fill"):
            st.session_state.tryon_selected_ids = product_ids[:8]
            st.session_state.tryon_generated = False
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        cat_filter = st.session_state.tryon_product_cat
        categories = [c for c in CATEGORY_LABELS if c == "all" or buckets[c]]
        st.markdown('<div class="tryon-cat-row">', unsafe_allow_html=True)
        cat_cols = st.columns(len(categories))
        for ccol, cat in zip(cat_cols, categories, strict=True):
            with ccol:
                if st.button(
                    CATEGORY_LABELS[cat],
                    key=f"tryon_cat_{cat}",
                    type="primary" if cat_filter == cat else "secondary",
                    use_container_width=True,
                ):
                    st.session_state.tryon_product_cat = cat
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        pool = buckets.get(cat_filter, all_products)
        selected_ids = set(st.session_state.tryon_selected_ids)
        st.markdown('<div class="pool-scroll-wrap">', unsafe_allow_html=True)
        for index, product in enumerate(pool[:12]):
            pid = product.num_iid or product.detail_url
            in_tryon = pid in selected_ids
            title = product.title if len(product.title) <= 22 else f"{product.title[:22]}…"
            cat_label = CATEGORY_LABELS.get("all", "推荐")
            thumb = (
                f'<img src="{html.escape(product.pic_url)}" alt="" />'
                if product.pic_url
                else "🛍"
            )
            st.markdown(
                f"""
                <div class="pool-item{" in-tryon" if in_tryon else ""}">
                  <div class="thumb">{thumb}</div>
                  <div class="info">
                    <div class="cat">{cat_label}</div>
                    <div class="name">{html.escape(title)}</div>
                    <div class="price">¥{product.price:.2f}</div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown('<div class="pool-add">', unsafe_allow_html=True)
            if st.button(
                "已选" if in_tryon else "试穿",
                key=f"tryon_pick_{index}_{pid}",
                use_container_width=True,
            ):
                _toggle_product(pid)
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        if not pool:
            st.caption("当日暂无推荐商品")
        st.markdown("</div>", unsafe_allow_html=True)

    with col_preview:
        st.markdown('<span class="tryon-col-3" aria-hidden="true"></span>', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="preview-head">
              <h3>⑤ AI 换装预览</h3>
            </div>
            """,
            unsafe_allow_html=True,
        )

        selected_products = [p for p in all_products if (p.num_iid or p.detail_url) in selected_ids]
        sel_parts = [
            f'<div class="sel-item">{html.escape(p.title[:14])}</div>' for p in selected_products[:3]
        ]
        if len(selected_products) < 4:
            sel_parts.append('<div class="sel-item empty">+ 配饰</div>')
        st.markdown(f'<div class="sel-bar">{"".join(sel_parts)}</div>', unsafe_allow_html=True)

        scene_name = scenes[scene_index][1]
        status = "完成" if st.session_state.tryon_generated and card.look_image_url else "待生成"
        st.markdown(
            f"""
            <div class="ai-preview-main">
              <div class="lbl"><span>AI 换装结果</span><span>{status}</span></div>
              <div class="canvas">
            """,
            unsafe_allow_html=True,
        )

        if st.session_state.tryon_generated and card.look_image_url:
            st.image(card.look_image_url, use_container_width=True)
            st.markdown(
                f'<div class="hint" style="color:var(--accent)">完成 · {html.escape(scene_name)} 背景</div>',
                unsafe_allow_html=True,
            )
        elif st.session_state.tryon_generated:
            st.markdown(
                '<div class="avatar" style="opacity:0.35">👗</div>'
                '<div class="hint">当日 AI 效果图暂不可用</div>',
                unsafe_allow_html=True,
            )
        else:
            avatar = st.session_state.tryon_model_avatar if virtual else "📷"
            st.markdown(
                f"""
                <div class="avatar" style="opacity:0.35">{avatar}</div>
                <div class="hint">中间选商品后点击「开始 AI 换装」<br/>背景将合成所选景点</div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("</div></div>", unsafe_allow_html=True)

        st.markdown('<div class="action-row">', unsafe_allow_html=True)
        if st.button("开始 AI 换装", type="primary", key="tryon_generate"):
            with st.spinner("AI 换装生成中…"):
                time.sleep(0.8)
            st.session_state.tryon_generated = True
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        hint = (
            f"{'虚拟模特' if virtual else '真人试穿'} · "
            f"{body_height}cm · {body_weight}kg · {scene_name}"
        )
        st.markdown(f'<p class="note">{html.escape(hint)}</p>', unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)
