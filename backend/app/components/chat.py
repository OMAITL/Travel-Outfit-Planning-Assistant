"""Chat panel — message history and input."""

from __future__ import annotations

from collections.abc import Callable

import streamlit as st

from src.graph.state import PlanningState


def render_message_history(state: PlanningState | None) -> None:
    if state is None or not state.messages:
        st.markdown(
            "👋 你好！告诉我 **目的地、日期** 和风格偏好，我来帮你规划每日穿搭。\n\n"
            "例如：*7月10–12日去大理，休闲风，拍照逛街，单件预算200元*"
        )
        return

    for message in state.messages:
        if message.role == "system":
            continue
        with st.chat_message(message.role):
            st.markdown(message.content)


def render_chat_input(
    *,
    disabled: bool,
    on_submit: Callable[[str], None],
    placeholder: str = "描述你的行程…",
) -> None:
    prompt = st.chat_input(placeholder, disabled=disabled)
    if prompt:
        on_submit(prompt)
