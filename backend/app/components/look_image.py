"""AI outfit look image — v1 ai-frame style."""

from __future__ import annotations

import html

import streamlit as st

from src.graph.state import TripPreferences


def _scene_caption(preferences: TripPreferences | None, destination: str) -> str:
    activities = preferences.activities if preferences else []
    gender = preferences.gender if preferences and preferences.gender else "旅行者"
    style = preferences.style if preferences else "休闲"

    scene_map = {
        "拍照": "网红拍照打卡地",
        "逛街": "商业步行街",
        "徒步": "自然步道",
        "观光": "城市地标",
        "美食": "本地美食街",
        "海边": "海滨栈道",
        "露营": "户外营地",
    }
    scene = destination or "旅行目的地"
    for activity in activities:
        if activity in scene_map:
            scene = scene_map[activity]
            break

    return f"AI 生成 · {gender} · {style}风 · {scene} · 真人穿搭示意，仅供参考"


def render_look_image(
    image_url: str | None,
    *,
    destination: str = "",
    preferences: TripPreferences | None = None,
    on_retry: bool = False,
    compact: bool = False,
    hide_title: bool = False,
    frame: bool = False,
    full_height: bool = False,
) -> None:
    if not hide_title:
        if compact:
            st.markdown("**📸 AI 穿搭效果图**")
        else:
            st.markdown("#### 📸 AI 穿搭效果图")

    caption = html.escape(_scene_caption(preferences, destination))
    min_h = "400px" if full_height else "240px"

    if frame:
        if image_url:
            st.markdown(
                f"""
                <div class="ai-frame" style="min-height:{min_h}">
                  <img src="{html.escape(image_url)}" alt="AI 穿搭效果图" />
                  <div class="scene-label">{caption}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            return
        st.markdown(
            f"""
            <div class="ai-frame" style="min-height:{min_h}">
              <div class="placeholder">
                <div class="icon">📸</div>
                <p>{"今日穿搭预览" if compact else "AI 穿搭效果图"}</p>
                <p style="font-size:0.78rem;opacity:0.85">生成中或暂时失败</p>
              </div>
              <div class="scene-label">{caption}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if on_retry:
            st.caption("重新规划可再次尝试生图")
        return

    if image_url:
        st.image(image_url, use_container_width=True)
        st.caption(_scene_caption(preferences, destination))
        return

    st.markdown(
        """
        <div class="ai-frame">
          <div class="placeholder">
            <div class="icon">🖼️</div>
            <p>AI 穿搭效果图生成中或暂时失败</p>
            <p style="font-size:0.78rem;opacity:0.85">可参考文字方案；请确认即梦 API 配置</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if on_retry:
        st.caption("重新规划可再次尝试生图")
