"""Static v1 prototype preview — shown before real report exists."""

from __future__ import annotations

import streamlit as st

DEMO_DAYS = (
    {
        "date": "6/5",
        "weekday": "周五",
        "weather": "🌧 16–27°C",
        "spots": ("洱海", "古城"),
    },
    {
        "date": "6/6",
        "weekday": "周六",
        "weather": "☀ 18–28°C",
        "spots": ("三塔", "古城"),
    },
    {
        "date": "6/7",
        "weekday": "周日",
        "weather": "⛅ 17–26°C",
        "spots": ("洱海",),
    },
)


def _render_weather_strip_html(selected: int) -> None:
    parts: list[str] = []
    for index, day in enumerate(DEMO_DAYS):
        active = " active" if index == selected else ""
        chips = "".join(f'<span class="spot-chip-sm">{s}</span>' for s in day["spots"])
        parts.append(
            f"""
            <div class="weather-mini{active}">
              <div class="date">{day["date"]}</div>
              <div class="wd">{day["weekday"]}</div>
              <div class="temp">{day["weather"]}</div>
              <div class="day-spot-row">{chips}</div>
            </div>
            """
        )
    st.markdown(
        f'<div class="weather-strip-html">{"".join(parts)}</div>',
        unsafe_allow_html=True,
    )


def _render_magazine_demo() -> None:
    st.markdown(
        """
        <article class="magazine magazine-demo">
          <div class="mag-header">
            <h3>6月5日 · 周五</h3>
            <div class="weather-line">🌧 雨 16–27°C · 降水 60%</div>
          </div>
          <div class="content-tabs-static">
            <span class="active">概要</span>
            <span>推荐商品</span>
          </div>
          <div class="tab-panel-static">
            <div class="mag-body">
              <div class="mag-text">
                <div class="section">
                  <div class="section-title">旅行提醒</div>
                  <ul class="tips-list">
                    <li>昼夜温差大，建议洋葱式叠穿，方便中午脱外套</li>
                    <li>可能降雨，备轻便雨衣或防水外套</li>
                  </ul>
                </div>
                <div class="section">
                  <div class="section-title">推荐理由</div>
                  <div class="reason-box">洱海骑行需要防风防泼水的薄外套，内搭白色 T 恤 + 牛仔裤经典耐看；卡其色系与湖光山色呼应，拍照出片。</div>
                </div>
                <div class="section">
                  <div class="section-title">单品清单</div>
                  <div class="items-grid">
                    <div class="item-cell"><span class="lbl">上装</span><br/>白色棉质短袖 T 恤 + 浅卡其防水风衣</div>
                    <div class="item-cell"><span class="lbl">下装</span><br/>蓝色直筒牛仔裤</div>
                    <div class="item-cell"><span class="lbl">鞋</span><br/>白色帆布鞋（防泼水）</div>
                    <div class="item-cell"><span class="lbl">配饰</span><br/>卡其棒球帽 · 米色斜挎包</div>
                  </div>
                </div>
                <div class="scores-row">
                  <span>风格 ★★★★☆</span><span>舒适 ★★★★★</span><span>出片 ★★★★☆</span><span>配色 白·卡其·蓝</span>
                </div>
              </div>
              <div class="mag-visual">
                <div class="spot-pills">
                  <span class="spot-pill active">洱海廊道</span>
                  <span class="spot-pill">大理古城</span>
                </div>
                <div class="ai-frame">
                  <div class="placeholder">
                    <div class="icon">📸</div>
                    <p>今日穿搭预览</p>
                    <p style="font-size:0.78rem;opacity:0.85">背景：洱海生态廊道</p>
                  </div>
                  <div class="scene-label">AI 生成 · 女 · 休闲风 · 洱海生态廊道</div>
                </div>
              </div>
            </div>
          </div>
        </article>
        <p class="footer-note demo-badge-line">↑ 布局预览 · 填写左侧表单并「开始规划穿搭」后替换为真实报告</p>
        """,
        unsafe_allow_html=True,
    )


def render_report_demo_preview() -> None:
    """Full right-column prototype shell (visual only)."""
    if "preview_day_index" not in st.session_state:
        st.session_state.preview_day_index = 0

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

    selected = st.session_state.preview_day_index
    _render_weather_strip_html(selected)

    st.markdown('<div class="weather-strip-btns demo-day-btns">', unsafe_allow_html=True)
    cols = st.columns(3)
    for index, (col, day) in enumerate(zip(cols, DEMO_DAYS, strict=True)):
        with col:
            label = f"{day['date']}\n{day['weekday']}\n{day['weather']}"
            if st.button(
                label,
                key=f"demo_day_{index}",
                type="primary" if index == selected else "secondary",
                use_container_width=True,
            ):
                st.session_state.preview_day_index = index
                st.rerun()
    st.markdown("</div></div>", unsafe_allow_html=True)

    _render_magazine_demo()
