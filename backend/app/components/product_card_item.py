"""Single product card — shared layout for live OneBound data and UI placeholders."""

from __future__ import annotations

import html

import streamlit as st

from src.graph.state import ProductCard


def _budget_status(price: float, budget: float | None) -> tuple[str, str]:
    if not budget or budget <= 0:
        return "—", "neutral"
    ratio = price / budget * 100
    if ratio <= 80:
        return f"占预算 {ratio:.0f}%", "good"
    if ratio <= 100:
        return f"占预算 {ratio:.0f}%", "warn"
    return f"超预算 {ratio - 100:.0f}%", "over"


def render_product_card_item(
    product: ProductCard,
    *,
    budget_per_item: float | None = None,
    index: int = 0,
    key_prefix: str = "",
) -> None:
    """Render one product card. Expects OneBound fields: pic_url, title, price, detail_url."""
    title = product.title if len(product.title) <= 32 else f"{product.title[:32]}…"
    budget_text, budget_class = _budget_status(product.price, budget_per_item)

    st.markdown(
        f'<div class="product-card product-card--live" data-index="{index}">',
        unsafe_allow_html=True,
    )
    st.image(product.pic_url, use_container_width=True)
    st.markdown(
        f"""
        <div class="product-card-body">
          <p class="product-title">{html.escape(title)}</p>
          <p class="product-price">¥{product.price:.2f}</p>
          <p class="budget-tag budget-{budget_class}">{html.escape(budget_text)}</p>
          <p class="product-meta">价格仅供参考</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.link_button(
        "去淘宝购买",
        product.detail_url,
        use_container_width=True,
        type="primary",
        key=f"buy_{key_prefix}_{product.num_iid or index}_{product.price}",
    )
    st.markdown("</div>", unsafe_allow_html=True)


def render_product_card_placeholder(*, index: int = 0, keyword: str | None = None) -> None:
    """Skeleton slot — same footprint as a live card until OneBound returns data."""
    label = keyword or "穿搭关键词"
    st.markdown(
        f"""
        <div class="product-card product-card--placeholder" data-index="{index}">
          <div class="product-image-slot">
            <span class="product-image-slot-icon">🛍</span>
          </div>
          <div class="product-card-body">
            <p class="product-title product-title--ghost">待匹配 · {html.escape(label[:14])}</p>
            <p class="product-price product-price--ghost">¥ —</p>
            <p class="budget-tag budget-neutral">占预算 —</p>
            <p class="product-meta">OneBound 接入后自动填充</p>
          </div>
          <div class="product-buy-placeholder">去淘宝购买</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
