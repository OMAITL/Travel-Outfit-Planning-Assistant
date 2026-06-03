"""Streamlit entry — chat (left) + travel report (right)."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import src.graph  # noqa: E402, F401 — triggers PlanningState.model_rebuild()
from app.components.chat import render_chat_input, render_message_history  # noqa: E402
from app.components.daily_card import render_daily_card  # noqa: E402
from app.components.progress import render_progress_steps  # noqa: E402
from app.components.trip_form import render_trip_form  # noqa: E402
from app.components.weather_panel import render_weather_overview  # noqa: E402
from src.config import key_fingerprint, reload_settings  # noqa: E402
from src.graph.state import PlanningPhase, PlanningState  # noqa: E402
from src.graph.workflow import run_planning  # noqa: E402

APP_TITLE = "旅行穿搭规划助手"
SPINNER_TEXT = "正在规划，请稍候…（天气 / 穿搭 / 生图 / 商品匹配可能需要 1–3 分钟）"


def _load_styles() -> None:
    css_path = Path(__file__).parent / "styles.css"
    if css_path.exists():
        st.markdown(
            f"<style>{css_path.read_text(encoding='utf-8')}</style>",
            unsafe_allow_html=True,
        )


def _init_session() -> None:
    defaults: dict[str, object] = {
        "planning_state": None,
        "last_error": None,
        "run_pending": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _reset_planning() -> None:
    st.session_state.planning_state = None
    st.session_state.last_error = None
    st.session_state.run_pending = None


def _queue_message(message: str) -> None:
    text = message.strip()
    if text:
        st.session_state.run_pending = text
        st.rerun()


def _execute_pending_run() -> None:
    message = st.session_state.run_pending
    if not message:
        return

    st.session_state.run_pending = None
    st.session_state.last_error = None

    try:
        with st.spinner(SPINNER_TEXT):
            st.session_state.planning_state = run_planning(
                message,
                state=st.session_state.planning_state,
            )
    except Exception as exc:
        st.session_state.last_error = str(exc)

    st.rerun()


def _format_trip_summary(state: PlanningState) -> str | None:
    if state.report:
        report = state.report
        style = "休闲"
        if state.trip and state.trip.preferences.style:
            style = state.trip.preferences.style
        activities = ""
        if state.trip and state.trip.preferences.activities:
            activities = " · " + " / ".join(state.trip.preferences.activities)
        return (
            f"**{report.destination}** · "
            f"{report.start_date.month}/{report.start_date.day}–"
            f"{report.end_date.month}/{report.end_date.day} · "
            f"{report.trip_days} 天 · {style}{activities}"
        )

    trip = state.trip
    if trip is None:
        return None

    prefs = trip.preferences
    parts = [f"**{trip.destination}**"]
    parts.append(
        f"{trip.start_date.month}/{trip.start_date.day}–"
        f"{trip.end_date.month}/{trip.end_date.day}"
    )
    parts.append(f"{trip.trip_days} 天")
    if prefs.style:
        parts.append(prefs.style)
    if prefs.activities:
        parts.append(" / ".join(prefs.activities))
    if prefs.budget_per_item:
        parts.append(f"单件 ¥{prefs.budget_per_item:.0f}")
    if prefs.budget_total:
        parts.append(f"整套 ¥{prefs.budget_total:.0f}")
    return " · ".join(parts)


def _render_report_empty() -> None:
    st.markdown(
        """
        <div class="report-empty">
          <div class="report-empty-icon">🧳</div>
          <p>填写左侧行程表单，或自由对话描述你的旅行</p>
          <p style="font-size:0.9rem">报告将展示：穿搭详情 · 推荐商品</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_report_panel(state: PlanningState | None, *, is_planning: bool) -> None:
    head_left, head_right = st.columns([5, 1])
    with head_left:
        st.subheader("行程报告")
    with head_right:
        st.markdown('<div class="report-reset-wrap">', unsafe_allow_html=True)
        if st.button("重新规划", use_container_width=True, key="reset_btn"):
            _reset_planning()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    if is_planning:
        render_progress_steps(state, is_planning=True)
        st.info("正在生成报告，请稍候…")
        return

    if st.session_state.last_error:
        st.error(f"规划失败：{st.session_state.last_error}")
        settings = reload_settings()
        st.caption(
            f"当前 LLM Key 尾号：**{key_fingerprint(settings.openai_api_key)}** · "
            f"模型：{settings.openai_model}"
        )

    if state is None:
        _render_report_empty()
        return

    summary = _format_trip_summary(state)
    if summary:
        st.markdown(summary)

    if state.phase == PlanningPhase.COLLECTING:
        st.caption("请先在左侧补全行程信息")

    if state.weather and state.trip:
        with st.expander("🌤 行程天气趋势", expanded=False):
            render_weather_overview(state.weather, state.trip)
            estimated_days = sum(1 for day in state.weather if day.estimated)
            if estimated_days:
                st.caption(
                    f"其中 {estimated_days} 天为季节参考估算（高德仅支持近 4 天实况预报）"
                )

    if state.report:
        cards = state.report.daily_cards
        if not cards:
            st.warning("报告为空")
            return

        shopping_errors = [e for e in state.errors if "OneBound" in e or "onebound" in e.lower()]

        st.markdown('<div class="compact-report">', unsafe_allow_html=True)
        tab_labels = [f"{card.date.month}/{card.date.day}" for card in cards]
        tabs = st.tabs(tab_labels)
        for tab, card in zip(tabs, cards, strict=True):
            with tab:
                render_daily_card(card, trip=state.trip, shopping_errors=shopping_errors)

        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown(
            f'<p class="disclaimer">{state.report.disclaimer}</p>',
            unsafe_allow_html=True,
        )
        return

    if state.phase == PlanningPhase.COLLECTING:
        _render_report_empty()
        return

    _render_report_empty()


def _render_header() -> None:
    st.markdown(
        f"""
        <div class="app-header">
          <h1 class="app-title">🧳 {APP_TITLE}</h1>
          <p class="app-subtitle">结构化填写 · 天气驱动穿搭 · AI 效果图 · 按单品购同款</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_input_panel(state: PlanningState | None, *, is_busy: bool) -> None:
    tab_form, tab_chat = st.tabs(["📋 快速填写", "💬 自由对话"])

    with tab_form:
        render_trip_form(on_submit=_queue_message, disabled=is_busy)

    with tab_chat:
        render_message_history(state)
        render_chat_input(
            disabled=is_busy,
            on_submit=_queue_message,
            placeholder="也可直接描述：7月10-12日去大理，休闲风…",
        )


def main() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="🧳",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    _load_styles()
    _init_session()
    reload_settings()

    if st.session_state.run_pending:
        _render_header()
        chat_col, report_col = st.columns([2, 3], gap="medium")
        state: PlanningState | None = st.session_state.planning_state
        with chat_col:
            st.markdown('<div class="input-column">', unsafe_allow_html=True)
            st.subheader("行程输入")
            _render_input_panel(state, is_busy=True)
            st.markdown("</div>", unsafe_allow_html=True)
        with report_col:
            st.markdown('<div class="report-column">', unsafe_allow_html=True)
            _render_report_panel(state, is_planning=True)
            st.markdown("</div>", unsafe_allow_html=True)
        _execute_pending_run()
        return

    _render_header()

    st.markdown('<div class="layout-shell">', unsafe_allow_html=True)
    chat_col, report_col = st.columns([2, 3], gap="medium")
    state = st.session_state.planning_state
    is_busy = st.session_state.run_pending is not None

    with chat_col:
        st.markdown('<div class="input-column">', unsafe_allow_html=True)
        st.subheader("行程输入")
        _render_input_panel(state, is_busy=is_busy)
        st.markdown("</div>", unsafe_allow_html=True)

    with report_col:
        st.markdown('<div class="report-column">', unsafe_allow_html=True)
        _render_report_panel(state, is_planning=is_busy)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
