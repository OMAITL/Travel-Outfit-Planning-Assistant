"""Structured trip input form with tags and quick examples."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

import streamlit as st

from app.utils.trip_message import (
    ACTIVITY_OPTIONS,
    AVOID_OPTIONS,
    BODY_TYPE_OPTIONS,
    GENDER_OPTIONS,
    QUICK_EXAMPLES,
    SKIN_TONE_OPTIONS,
    STYLE_OPTIONS,
    build_trip_message,
)


def _apply_quick_example(name: str) -> None:
    example = QUICK_EXAMPLES.get(name)
    if not example:
        return
    today = date.today()
    start = today + timedelta(days=int(example["start_offset"]))
    duration = int(example["duration"])
    end = start + timedelta(days=duration - 1)

    st.session_state.form_destination = example["destination"]
    st.session_state.form_start = start
    st.session_state.form_end = end
    st.session_state.form_gender = example["gender"]
    st.session_state.form_styles = list(example["styles"])
    st.session_state.form_activities = list(example["activities"])
    st.session_state.form_budget_per_item = float(
        example.get("budget_per_item", example.get("budget", 200))
    )
    st.session_state.form_budget_total = float(example.get("budget_total", 0))
    st.session_state.form_party_size = int(example.get("party_size", 1))


def _init_form_state() -> None:
    today = date.today()
    defaults: dict[str, object] = {
        "form_destination": "",
        "form_start": today + timedelta(days=1),
        "form_end": today + timedelta(days=3),
        "form_gender": "女",
        "form_styles": ["休闲"],
        "form_activities": ["拍照", "逛街"],
        "form_budget_per_item": 200,
        "form_budget_total": 800,
        "form_party_size": 1,
        "form_height_cm": 165,
        "form_weight_kg": 55,
        "form_body_type": "不限",
        "form_skin_tone": "不限",
        "form_avoid_items": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_trip_form(*, on_submit: Callable[[str], None], disabled: bool = False) -> None:
    """Render structured trip form; calls on_submit with composed message."""
    _init_form_state()
    st.caption("填写关键信息，一键生成高质量行程描述")

    quick_cols = st.columns(len(QUICK_EXAMPLES))
    for column, name in zip(quick_cols, QUICK_EXAMPLES, strict=True):
        with column:
            if st.button(name, use_container_width=True, disabled=disabled, key=f"quick_{name}"):
                _apply_quick_example(name)
                st.rerun()

    with st.form("trip_form", clear_on_submit=False):
        destination = st.text_input(
            "目的地 *",
            value=st.session_state.form_destination,
            placeholder="例如：大理、东京、成都",
        )

        col_start, col_end = st.columns(2)
        with col_start:
            start_date = st.date_input("出发日期 *", value=st.session_state.form_start)
        with col_end:
            end_date = st.date_input("返回日期 *", value=st.session_state.form_end)

        col_gender, col_party = st.columns(2)
        with col_gender:
            gender = st.selectbox(
                "性别",
                GENDER_OPTIONS,
                index=GENDER_OPTIONS.index(st.session_state.form_gender)
                if st.session_state.form_gender in GENDER_OPTIONS
                else 0,
            )
        with col_party:
            party_size = st.number_input(
                "出行人数",
                min_value=1,
                max_value=20,
                value=int(st.session_state.form_party_size),
            )

        styles = st.multiselect(
            "风格标签",
            STYLE_OPTIONS,
            default=st.session_state.form_styles,
            help="可多选，系统将综合你的风格偏好",
        )

        activities = st.multiselect(
            "旅行场景",
            ACTIVITY_OPTIONS,
            default=st.session_state.form_activities,
            help="选择主要活动场景，影响穿搭与 AI 效果图",
        )

        col_budget_item, col_budget_total = st.columns(2)
        with col_budget_item:
            budget_per_item = st.number_input(
                "单件预算（元）",
                min_value=0,
                max_value=5000,
                value=int(st.session_state.form_budget_per_item),
                step=50,
                help="每件单品的价格上限",
            )
        with col_budget_total:
            budget_total = st.number_input(
                "整套穿搭总预算（元）",
                min_value=0,
                max_value=20000,
                value=int(st.session_state.form_budget_total),
                step=100,
                help="一天整套穿搭的总价参考上限",
            )

        with st.expander("体型与穿搭偏好", expanded=False):
            col_h, col_w = st.columns(2)
            with col_h:
                height_cm = st.number_input(
                    "身高（cm）",
                    min_value=0,
                    max_value=230,
                    value=int(st.session_state.form_height_cm),
                )
            with col_w:
                weight_kg = st.number_input(
                    "体重（kg）",
                    min_value=0,
                    max_value=200,
                    value=int(st.session_state.form_weight_kg),
                )
            col_body, col_skin = st.columns(2)
            with col_body:
                body_type = st.selectbox(
                    "体型",
                    BODY_TYPE_OPTIONS,
                    index=BODY_TYPE_OPTIONS.index(st.session_state.form_body_type)
                    if st.session_state.form_body_type in BODY_TYPE_OPTIONS
                    else 0,
                )
            with col_skin:
                skin_tone = st.selectbox(
                    "肤色",
                    SKIN_TONE_OPTIONS,
                    index=SKIN_TONE_OPTIONS.index(st.session_state.form_skin_tone)
                    if st.session_state.form_skin_tone in SKIN_TONE_OPTIONS
                    else 0,
                )
            avoid_items = st.multiselect(
                "穿搭避雷",
                AVOID_OPTIONS,
                default=st.session_state.form_avoid_items,
                help="例如：不穿裙子、拒穿牛仔",
            )

        submitted = st.form_submit_button(
            "开始规划穿搭",
            use_container_width=True,
            disabled=disabled,
            type="primary",
        )

        if submitted:
            if not destination.strip():
                st.error("请填写目的地")
                return
            if end_date < start_date:
                st.error("返回日期不能早于出发日期")
                return

            st.session_state.form_destination = destination
            st.session_state.form_start = start_date
            st.session_state.form_end = end_date
            st.session_state.form_gender = gender
            st.session_state.form_styles = styles or ["休闲"]
            st.session_state.form_activities = activities
            st.session_state.form_budget_per_item = budget_per_item
            st.session_state.form_budget_total = budget_total
            st.session_state.form_party_size = party_size
            st.session_state.form_height_cm = height_cm
            st.session_state.form_weight_kg = weight_kg
            st.session_state.form_body_type = body_type
            st.session_state.form_skin_tone = skin_tone
            st.session_state.form_avoid_items = avoid_items

            message = build_trip_message(
                destination=destination,
                start_date=start_date,
                end_date=end_date,
                gender=gender,
                styles=styles or ["休闲"],
                activities=activities,
                budget_per_item=float(budget_per_item) if budget_per_item > 0 else None,
                budget_total=float(budget_total) if budget_total > 0 else None,
                party_size=int(party_size),
                height_cm=float(height_cm) if height_cm > 0 else None,
                weight_kg=float(weight_kg) if weight_kg > 0 else None,
                body_type=body_type,
                skin_tone=skin_tone,
                avoid_items=avoid_items,
            )
            on_submit(message)
