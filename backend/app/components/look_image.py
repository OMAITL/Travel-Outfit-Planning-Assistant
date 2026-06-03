"""AI outfit look image — realistic travel photo display."""

from __future__ import annotations

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
    scene = "旅行目的地"
    for activity in activities:
        if activity in scene_map:
            scene = scene_map[activity]
            break

    return f"AI 生成 · {gender} · {style}风 · {destination} · {scene} · 真人穿搭示意，仅供参考"


def render_look_image(
    image_url: str | None,
    *,
    destination: str = "",
    preferences: TripPreferences | None = None,
    on_retry: bool = False,
    compact: bool = False,
) -> None:
    if compact:
        st.markdown("**📸 AI 穿搭效果图**")
    else:
        st.markdown("#### 📸 AI 穿搭效果图")

    if image_url:
        st.image(image_url, use_container_width=True)
        st.caption(_scene_caption(preferences, destination))
        return

    st.markdown(
        """
        <div class="look-placeholder">
          <div class="look-placeholder-icon">🖼️</div>
          <p>AI 穿搭效果图生成中或暂时失败</p>
          <p class="look-placeholder-sub">可参考上方文字方案；请确认即梦 / DashScope API 配置</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if on_retry:
        st.caption("重新规划可再次尝试生图")
