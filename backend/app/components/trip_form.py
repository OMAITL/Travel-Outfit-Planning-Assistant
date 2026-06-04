"""Trip input form — visual layout aligned with v1 prototype."""

from __future__ import annotations

import html
from collections.abc import Callable
from datetime import date, timedelta

import streamlit as st

from app.data.city_spots import CITY_CATALOG, CITY_KEYS
from app.utils.trip_message import (
    AVOID_OPTIONS,
    BODY_TYPE_OPTIONS,
    GENDER_OPTIONS,
    SKIN_TONE_OPTIONS,
    build_trip_context,
    build_trip_message,
    merge_avoid_items,
)


def _init_form_state() -> None:
    today = date.today()
    defaults: dict[str, object] = {
        "form_city_key": "dali",
        "form_spot_ids": list(CITY_CATALOG["dali"].default_spot_ids),
        "form_start": today + timedelta(days=1),
        "form_end": today + timedelta(days=3),
        "form_plan_mode": "auto",
        "form_style_text": "休闲",
        "form_budget_per_item": 200,
        "form_budget_total": 800,
        "form_height_cm": 165,
        "form_weight_kg": 55,
        "form_body_type": "不限",
        "form_skin_tone": "不限",
        "form_avoid_items": [],
        "form_avoid_custom": "",
        "form_gender": "女",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    st.session_state.pop("form_party_size", None)


def _render_spot_chips(city_key: str, spot_ids: list[str]) -> None:
    city = CITY_CATALOG[city_key]
    id_set = set(spot_ids)
    chips = [
        f'<span class="spot-chip">{spot.emoji} {html.escape(spot.name)}</span>'
        for spot in city.spots
        if spot.id in id_set
    ]
    st.markdown(
        f"""
        <div class="spots-section">
          <div class="spots-hint">已选「{html.escape(city.name)}」· 可多选 · 影响 AI 背景</div>
          <div class="spot-chips-selected">{"".join(chips)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_trip_form(*, on_submit: Callable[[str], None], disabled: bool = False) -> None:
    _init_form_state()

    city_key = st.session_state.form_city_key
    if city_key not in CITY_CATALOG:
        city_key = "dali"
        st.session_state.form_city_key = city_key

    city = CITY_CATALOG[city_key]
    spot_options = {spot.id: f"{spot.emoji} {spot.name}" for spot in city.spots}
    valid_spots = [sid for sid in st.session_state.form_spot_ids if sid in spot_options]
    if not valid_spots:
        valid_spots = list(city.default_spot_ids)
        st.session_state.form_spot_ids = valid_spots

    st.markdown('<label class="field-label">目的地（城市）</label>', unsafe_allow_html=True)
    city_labels = {k: CITY_CATALOG[k].name for k in CITY_KEYS}
    selected_city = st.selectbox(
        "目的地（城市）",
        options=CITY_KEYS,
        format_func=lambda k: city_labels[k],
        index=CITY_KEYS.index(city_key),
        label_visibility="collapsed",
        disabled=disabled,
        key="ui_city_select",
    )
    if selected_city != city_key:
        st.session_state.form_city_key = selected_city
        st.session_state.form_spot_ids = list(CITY_CATALOG[selected_city].default_spot_ids)
        st.rerun()

    st.markdown('<label class="field-label spot-label">选择景点</label>', unsafe_allow_html=True)
    _render_spot_chips(city_key, valid_spots)

    spot_ids = st.multiselect(
        "选择景点",
        options=list(spot_options.keys()),
        default=valid_spots,
        format_func=lambda sid: spot_options[sid],
        label_visibility="collapsed",
        disabled=disabled,
        placeholder="+ 选择 / 管理景点",
        key=f"ui_spots_{city_key}",
    )
    if spot_ids != valid_spots:
        st.session_state.form_spot_ids = spot_ids
        st.rerun()

    st.markdown(
        f'<div class="selected-count">已选 {len(spot_ids)} 个景点</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="row2-fields">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<label class="field-label">出发</label>', unsafe_allow_html=True)
        start_date = st.date_input(
            "出发",
            value=st.session_state.form_start,
            label_visibility="collapsed",
            disabled=disabled,
            key="ui_start_date",
        )
    with c2:
        st.markdown('<label class="field-label">返回</label>', unsafe_allow_html=True)
        end_date = st.date_input(
            "返回",
            value=st.session_state.form_end,
            label_visibility="collapsed",
            disabled=disabled,
            key="ui_end_date",
        )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<label class="field-label">行程安排</label>', unsafe_allow_html=True)
    st.markdown('<div class="plan-mode-row">', unsafe_allow_html=True)
    pm1, pm2 = st.columns(2)
    plan_mode = st.session_state.form_plan_mode
    with pm1:
        if st.button(
            "✋ 我自己安排",
            key="plan_manual",
            type="primary" if plan_mode == "manual" else "secondary",
            use_container_width=True,
            disabled=disabled,
        ):
            st.session_state.form_plan_mode = "manual"
            st.rerun()
    with pm2:
        if st.button(
            "✨ 系统智能分配",
            key="plan_auto",
            type="primary" if plan_mode == "auto" else "secondary",
            use_container_width=True,
            disabled=disabled,
        ):
            st.session_state.form_plan_mode = "auto"
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    if plan_mode == "manual":
        st.markdown(
            """
            <div class="plan-hint">先选日期，再为<strong>当前这一天</strong>指定景点</div>
            <div class="manual-empty">手动排期 UI 预览 · 功能后续接入</div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<p class="plan-hint plan-hint-compact">'
            "系统将根据所选景点自动排期，结果在右侧「行程报告」展示</p>",
            unsafe_allow_html=True,
        )

    st.markdown('<label class="field-label">风格标签</label>', unsafe_allow_html=True)
    style_text = st.text_input(
        "风格标签",
        value=st.session_state.form_style_text,
        label_visibility="collapsed",
        disabled=disabled,
        key="ui_style",
    )

    st.markdown('<div class="row2-fields">', unsafe_allow_html=True)
    b1, b2 = st.columns(2)
    with b1:
        st.markdown('<label class="field-label">单件预算</label>', unsafe_allow_html=True)
        budget_per_item = st.number_input(
            "单件预算",
            min_value=0,
            max_value=5000,
            value=int(st.session_state.form_budget_per_item),
            step=50,
            label_visibility="collapsed",
            disabled=disabled,
            key="ui_budget_item",
        )
    with b2:
        st.markdown('<label class="field-label">整套预算</label>', unsafe_allow_html=True)
        budget_total = st.number_input(
            "整套预算",
            min_value=0,
            max_value=20000,
            value=int(st.session_state.form_budget_total),
            step=100,
            label_visibility="collapsed",
            disabled=disabled,
            key="ui_budget_total",
        )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="prefs-panel-marker">', unsafe_allow_html=True)
    with st.expander("体型与穿搭偏好", expanded=True):
        h1, h2 = st.columns(2)
        with h1:
            st.markdown('<label class="field-label">身高 (cm)</label>', unsafe_allow_html=True)
            height_cm = st.number_input(
                "身高",
                min_value=0,
                max_value=230,
                value=int(st.session_state.form_height_cm),
                label_visibility="collapsed",
                disabled=disabled,
                key="ui_height",
            )
        with h2:
            st.markdown('<label class="field-label">体重 (kg)</label>', unsafe_allow_html=True)
            weight_kg = st.number_input(
                "体重",
                min_value=0,
                max_value=200,
                value=int(st.session_state.form_weight_kg),
                label_visibility="collapsed",
                disabled=disabled,
                key="ui_weight",
            )
        t1, t2 = st.columns(2)
        with t1:
            body_type = st.selectbox(
                "体型",
                BODY_TYPE_OPTIONS,
                index=BODY_TYPE_OPTIONS.index(st.session_state.form_body_type)
                if st.session_state.form_body_type in BODY_TYPE_OPTIONS
                else 0,
                disabled=disabled,
                key="ui_body",
            )
        with t2:
            skin_tone = st.selectbox(
                "肤色",
                SKIN_TONE_OPTIONS,
                index=SKIN_TONE_OPTIONS.index(st.session_state.form_skin_tone)
                if st.session_state.form_skin_tone in SKIN_TONE_OPTIONS
                else 0,
                disabled=disabled,
                key="ui_skin",
            )
        avoid_items_selected = st.multiselect(
            "穿搭避雷",
            AVOID_OPTIONS,
            default=st.session_state.form_avoid_items,
            disabled=disabled,
            key="ui_avoid",
        )
        avoid_custom = st.text_input(
            "其他避雷项",
            value=st.session_state.form_avoid_custom,
            placeholder="例如：不穿露背、不要戴帽子",
            disabled=disabled,
            key="ui_avoid_custom",
        )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="submit-primary-wrap">', unsafe_allow_html=True)
    if st.button(
        "开始规划穿搭",
        type="primary",
        use_container_width=True,
        disabled=disabled,
        key="ui_submit_plan",
    ):
        destination = city.name
        if end_date < start_date:
            st.error("返回日期不能早于出发日期")
            return

        spot_names = [spot.name for spot in city.spots if spot.id in spot_ids]
        styles = [style_text.strip() or "休闲"]
        activities = ["拍照", "逛街"]
        gender = st.session_state.form_gender
        avoid_items = merge_avoid_items(avoid_items_selected, avoid_custom)

        st.session_state.form_spot_ids = list(spot_ids)
        st.session_state.form_start = start_date
        st.session_state.form_end = end_date
        st.session_state.form_style_text = style_text
        st.session_state.form_budget_per_item = budget_per_item
        st.session_state.form_budget_total = budget_total
        st.session_state.form_height_cm = height_cm
        st.session_state.form_weight_kg = weight_kg
        st.session_state.form_body_type = body_type
        st.session_state.form_skin_tone = skin_tone
        st.session_state.form_avoid_items = avoid_items_selected
        st.session_state.form_avoid_custom = avoid_custom

        message = build_trip_message(
            destination=destination,
            start_date=start_date,
            end_date=end_date,
            gender=gender,
            styles=styles,
            activities=activities,
            budget_per_item=float(budget_per_item) if budget_per_item > 0 else None,
            budget_total=float(budget_total) if budget_total > 0 else None,
            height_cm=float(height_cm) if height_cm > 0 else None,
            weight_kg=float(weight_kg) if weight_kg > 0 else None,
            body_type=body_type,
            skin_tone=skin_tone,
            avoid_items=avoid_items,
        )
        if spot_names:
            message = f"{message}，景点：{'、'.join(spot_names)}"

        st.session_state.pending_trip_context = build_trip_context(
            destination=destination,
            start_date=start_date,
            end_date=end_date,
            gender=gender,
            styles=styles,
            activities=activities,
            budget_per_item=float(budget_per_item) if budget_per_item > 0 else None,
            budget_total=float(budget_total) if budget_total > 0 else None,
            height_cm=float(height_cm) if height_cm > 0 else None,
            weight_kg=float(weight_kg) if weight_kg > 0 else None,
            body_type=body_type,
            skin_tone=skin_tone,
            avoid_items=avoid_items,
        )
        on_submit(message)
    st.markdown("</div>", unsafe_allow_html=True)
