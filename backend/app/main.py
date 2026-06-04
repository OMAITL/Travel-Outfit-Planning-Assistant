"""Streamlit entry — v1 magazine layout + v3 try-on workspace."""

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
from app.components.report_preview import render_report_demo_preview  # noqa: E402
from app.components.trip_form import render_trip_form  # noqa: E402
from app.components.tryon import render_tryon_workspace  # noqa: E402
from app.components.weather_panel import render_weather_overview  # noqa: E402
from src.config import key_fingerprint, reload_settings  # noqa: E402
from src.graph.state import PlanningPhase, PlanningState, TripContext  # noqa: E402
from src.graph.workflow import run_planning  # noqa: E402

APP_TITLE = "旅行穿搭规划助手"
APP_TAGLINE = "AI 旅游穿搭与淘宝导购 · 按景点定制出片造型"
PLANNING_STATUS = "正在规划行程穿搭…"
PLANNING_HINT = "天气 / 穿搭 / 生图 / 商品匹配可能需要 1–3 分钟，请勿关闭页面"
WEEKDAY_ZH = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


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
        "pending_trip_context": None,
        "app_view": "planning",
        "selected_day_index": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _reset_planning() -> None:
    st.session_state.planning_state = None
    st.session_state.last_error = None
    st.session_state.run_pending = None
    st.session_state.pending_trip_context = None
    st.session_state.selected_day_index = 0
    st.session_state.app_view = "planning"


def _back_to_planning() -> None:
    st.session_state.app_view = "planning"
    st.rerun()


def _queue_message(message: str) -> None:
    text = message.strip()
    if text:
        st.session_state.run_pending = text
        st.rerun()


def _initial_state_for_run(
    message: str,
    *,
    pending_trip: TripContext | None,
    existing: PlanningState | None,
) -> PlanningState | None:
    if pending_trip is not None:
        return PlanningState(trip=pending_trip, phase=PlanningPhase.PLANNING)
    return existing


def _execute_pending_run() -> None:
    message = st.session_state.run_pending
    if not message:
        return

    st.session_state.run_pending = None
    pending_trip: TripContext | None = st.session_state.pop("pending_trip_context", None)
    st.session_state.last_error = None

    initial_state = _initial_state_for_run(
        message,
        pending_trip=pending_trip,
        existing=st.session_state.planning_state,
    )

    try:
        with st.status(PLANNING_STATUS, expanded=True) as status:
            st.caption(PLANNING_HINT)
            result = run_planning(message, state=initial_state)
            st.session_state.planning_state = result
            st.session_state.selected_day_index = 0
            if result.report:
                status.update(label="规划完成", state="complete")
            elif result.phase == PlanningPhase.COLLECTING:
                status.update(label="需补充行程信息", state="complete")
            elif result.errors:
                status.update(label="规划完成（部分步骤有问题）", state="complete")
            else:
                status.update(label="规划结束", state="complete")
    except Exception as exc:
        st.session_state.last_error = str(exc)
        st.error(f"规划失败：{exc}")

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
            f"{report.destination} · "
            f"{report.start_date.month}/{report.start_date.day}–"
            f"{report.end_date.month}/{report.end_date.day} · "
            f"{report.trip_days} 天 · {style}{activities}"
        )

    trip = state.trip
    if trip is None:
        return None

    prefs = trip.preferences
    parts = [trip.destination]
    parts.append(
        f"{trip.start_date.month}/{trip.start_date.day}–"
        f"{trip.end_date.month}/{trip.end_date.day}"
    )
    parts.append(f"{trip.trip_days} 天")
    if prefs.style:
        parts.append(prefs.style)
    if prefs.activities:
        parts.append(" / ".join(prefs.activities))
    return " · ".join(parts)


def _render_hero(*, title: str = APP_TITLE, tagline: str = APP_TAGLINE, back: bool = False) -> None:
    back_html = ""
    if back:
        back_html = '<div class="tryon-back-btn-marker"></div>'
    st.markdown(
        f"""
        <header class="hero-fullbleed">
          <div class="hero-inner">
            <div>
              <h1>{title}</h1>
              <p>{tagline}</p>
            </div>
            {back_html}
          </div>
        </header>
        """,
        unsafe_allow_html=True,
    )


def _render_report_head(*, show_edit_hint: bool = False) -> None:
    st.markdown('<div class="report-head-row">', unsafe_allow_html=True)
    st.markdown('<h2>行程报告</h2>', unsafe_allow_html=True)
    st.markdown('<div class="report-actions-row">', unsafe_allow_html=True)
    a1, a2, a3 = st.columns(3)
    with a1:
        st.button("↻ 重新智能分配", key="btn_regen_plan", disabled=False)
    with a2:
        st.button("✏️ 编辑行程", key="btn_edit_itinerary", disabled=False)
    with a3:
        if st.button("重新规划", key="reset_btn"):
            _reset_planning()
            st.rerun()
    st.markdown("</div></div>", unsafe_allow_html=True)
    if show_edit_hint:
        st.markdown(
            '<p class="itinerary-edit-hint visible">'
            "编辑模式：点击各日卡片上的 × 删除景点，或点 + 添加</p>",
            unsafe_allow_html=True,
        )


def _render_report_empty() -> None:
    pass  # replaced by demo preview


def _day_button_label(card, weather) -> str:
    weekday = WEEKDAY_ZH[card.date.weekday()]
    date_line = f"{card.date.month}/{card.date.day}"
    if weather is None:
        return f"{date_line}\n{weekday}\n—"
    condition = (
        weather.condition.value
        if hasattr(weather.condition, "value")
        else str(weather.condition)
    )
    icon = "🌧" if "雨" in condition else "☀" if "晴" in condition else "⛅" if "云" in condition else "🌤"
    temp = f"{icon} {weather.temp_min:.0f}–{weather.temp_max:.0f}°C"
    return f"{date_line}\n{weekday}\n{temp}"


def _render_day_weather_strip(cards: list) -> int:
    selected = st.session_state.selected_day_index
    if selected >= len(cards):
        selected = 0
        st.session_state.selected_day_index = 0

    st.markdown('<div class="weather-strip-btns">', unsafe_allow_html=True)
    cols = st.columns(len(cards))
    for index, (col, card) in enumerate(zip(cols, cards, strict=True)):
        with col:
            if st.button(
                _day_button_label(card, card.weather),
                key=f"day_strip_{index}",
                type="primary" if index == selected else "secondary",
                use_container_width=True,
            ):
                st.session_state.selected_day_index = index
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    return st.session_state.selected_day_index


def _render_report_panel(state: PlanningState | None) -> None:
    st.markdown('<span class="report-main-marker" aria-hidden="true"></span>', unsafe_allow_html=True)

    _render_report_head(show_edit_hint=False)

    if st.session_state.last_error:
        st.error(f"规划失败：{st.session_state.last_error}")
        settings = reload_settings()
        st.caption(
            f"当前 LLM Key 尾号：**{key_fingerprint(settings.openai_api_key)}** · "
            f"模型：{settings.openai_model}"
        )
    elif state and state.errors:
        for err in state.errors:
            st.error(err)

    if state is None:
        render_report_demo_preview()
        return

    summary = _format_trip_summary(state)
    if summary:
        st.markdown(f'<p class="report-summary-line">{summary}</p>', unsafe_allow_html=True)

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

        if state.report:
            st.markdown(
                '<p class="report-mode-note">✨ 系统已分配行程 · 下方卡片为排期结果，可「编辑行程」微调</p>',
                unsafe_allow_html=True,
            )

        st.markdown(
            """
            <div class="itinerary-result">
              <div class="itinerary-result-head">
                <span class="title">行程分配</span>
                <span class="auto-badge">AI 推荐</span>
              </div>
            """,
            unsafe_allow_html=True,
        )
        day_index = _render_day_weather_strip(cards)
        st.markdown("</div>", unsafe_allow_html=True)

        render_daily_card(
            cards[day_index],
            trip=state.trip,
            shopping_errors=shopping_errors,
            day_index=day_index,
        )

        st.markdown(
            f'<p class="footer-note">{state.report.disclaimer}</p>',
            unsafe_allow_html=True,
        )
        return

    if state.phase == PlanningPhase.COLLECTING:
        render_report_demo_preview()
        return

    if state.errors and state.trip:
        render_progress_steps(state, is_planning=False)
        st.warning("规划未完成，请查看上方错误信息后重试。")
        return

    render_report_demo_preview()


def _render_input_panel(state: PlanningState | None) -> None:
    tab_form, tab_chat = st.tabs(["📋 快速填写", "💬 自由对话"])

    with tab_form:
        render_trip_form(on_submit=_queue_message, disabled=False)

    with tab_chat:
        render_message_history(state)
        render_chat_input(
            disabled=False,
            on_submit=_queue_message,
            placeholder="也可直接描述：7月10-12日去大理，休闲风…",
        )


def _render_planning_view(state: PlanningState | None) -> None:
    _render_hero()

    st.markdown('<div class="shell-wrap">', unsafe_allow_html=True)
    input_col, report_col = st.columns([1, 3], gap="medium")

    with input_col:
        st.markdown('<span class="shell-left-marker" aria-hidden="true"></span>', unsafe_allow_html=True)
        st.markdown('<p class="panel-title-text">行程输入</p>', unsafe_allow_html=True)
        _render_input_panel(state)

    with report_col:
        _render_report_panel(state)

    st.markdown("</div>", unsafe_allow_html=True)


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
        _render_hero()
        _execute_pending_run()
        return

    state: PlanningState | None = st.session_state.planning_state

    if st.session_state.app_view == "tryon" and state is not None:
        render_tryon_workspace(state, on_back=_back_to_planning)
        return

    _render_planning_view(state)


if __name__ == "__main__":
    main()
