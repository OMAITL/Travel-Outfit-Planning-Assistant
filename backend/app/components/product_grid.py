"""Product recommendation grid — styled for OneBound data, placeholders when empty."""

from __future__ import annotations

from urllib.parse import quote

import streamlit as st

from app.components.product_card_item import (
    render_product_card_item,
    render_product_card_placeholder,
)
from src.graph.state import ProductCard

MAX_PRODUCTS = 5


def _fallback_search_url(keywords: str) -> str:
    return f"https://s.taobao.com/search?q={quote(keywords)}"


def _render_stats(
    products: list[ProductCard],
    *,
    budget_per_item: float | None,
    placeholder_count: int = 0,
) -> None:
    if products:
        total = sum(p.price for p in products)
        avg = total / len(products)
        within_budget = (
            sum(1 for p in products if budget_per_item and p.price <= budget_per_item)
            if budget_per_item
            else len(products)
        )
        s1, s2, s3 = st.columns(3)
        s1.metric("推荐数量", f"{len(products)} 件")
        s2.metric("均价", f"¥{avg:.0f}")
        if budget_per_item:
            s3.metric("预算内", f"{within_budget}/{len(products)}")
        else:
            s3.metric("合计参考", f"¥{total:.0f}")
        return

    s1, s2, s3 = st.columns(3)
    s1.metric("推荐数量", "0 件")
    s2.metric("均价", "—")
    s3.metric("待匹配", f"{placeholder_count} 个槽位")


def render_product_grid(
    products: list[ProductCard],
    *,
    search_fallback: str | None = None,
    budget_per_item: float | None = None,
    shopping_errors: list[str] | None = None,
    show_placeholders: bool = True,
    key_prefix: str = "",
) -> None:
    """
    Product section for daily report cards.

    When ``products`` is non-empty, renders live OneBound ``ProductCard`` rows
    (pic_url, detail_url, price, title). When empty, shows styled placeholder
    slots in the same layout until the API is available again.
    """
    st.markdown(
        """
        <div class="product-section">
          <div class="product-section-header">
            <span class="product-section-icon">🛍</span>
            <span class="product-section-title">推荐商品</span>
            <span class="product-section-badge">最多 5 个</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if shopping_errors:
        for err in shopping_errors:
            if "OneBound" in err or "onebound" in err.lower():
                st.markdown(
                    f'<div class="product-api-notice">{err}</div>',
                    unsafe_allow_html=True,
                )

    has_live = bool(products)
    slot_count = len(products) if has_live else (MAX_PRODUCTS if show_placeholders else 0)
    _render_stats(products, budget_per_item=budget_per_item, placeholder_count=slot_count)

    if not has_live and show_placeholders:
        st.markdown(
            """
            <p class="product-preview-hint">
              商品接口暂不可用 · 下方为<strong>固定布局预览</strong>，
              OneBound 恢复后将自动替换为真实商品图与淘宝购买链接。
            </p>
            """,
            unsafe_allow_html=True,
        )

    if slot_count == 0:
        st.caption("暂未匹配到商品")
        if search_fallback:
            st.link_button(
                "在淘宝搜索相关商品",
                _fallback_search_url(search_fallback),
                use_container_width=True,
            )
        return

    columns = st.columns(min(slot_count, MAX_PRODUCTS))
    keyword_hint = search_fallback or "穿搭单品"

    for index, column in enumerate(columns):
        with column:
            if has_live and index < len(products):
                render_product_card_item(
                    products[index],
                    budget_per_item=budget_per_item,
                    index=index,
                    key_prefix=key_prefix,
                )
            else:
                render_product_card_placeholder(index=index, keyword=keyword_hint)

    if search_fallback:
        st.link_button(
            "🔍 在淘宝搜索更多相关商品",
            _fallback_search_url(search_fallback),
            use_container_width=False,
        )

    st.caption(
        "商品数据来自万邦 OneBound · 点击「去淘宝购买」将在新标签页打开 item.taobao.com 链接"
    )
