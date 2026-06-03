"""Per-outfit-item product recommendations (1–5 links per item)."""

from __future__ import annotations

from urllib.parse import quote

import streamlit as st

from app.components.product_card_item import (
    render_product_card_item,
    render_product_card_placeholder,
)
from app.utils.product_grouping import assign_products_to_items
from src.graph.state import DailyOutfit, ProductCard

MAX_PER_ITEM = 5
PLACEHOLDER_SLOTS = 2


def _fallback_search_url(keywords: str) -> str:
    return f"https://s.taobao.com/search?q={quote(keywords)}"


def render_products_by_item(
    outfit: DailyOutfit | None,
    products: list[ProductCard],
    *,
    budget_per_item: float | None = None,
    shopping_errors: list[str] | None = None,
    key_prefix: str = "",
    show_placeholders: bool = True,
    compact: bool = False,
) -> None:
    """Render each outfit item with 1–5 Taobao product cards."""
    groups = assign_products_to_items(outfit, products, max_per_item=MAX_PER_ITEM)

    if shopping_errors and not compact:
        for err in shopping_errors:
            if "OneBound" in err or "onebound" in err.lower():
                st.markdown(f'<div class="product-api-notice">{err}</div>', unsafe_allow_html=True)

    if not products and show_placeholders and not compact:
        st.caption("商品接口暂不可用 · 下方为按单品分组的布局预览")

    for item_index, (label, text, item_products) in enumerate(groups):
        title = text if len(text) <= 18 else f"{text[:18]}…"
        expander_label = f"{label} · {title}"

        with st.expander(expander_label, expanded=(item_index == 0 and compact)):
            slot_count = len(item_products) if item_products else PLACEHOLDER_SLOTS
            columns = st.columns(min(slot_count, MAX_PER_ITEM if not compact else 3))

            for col_index, column in enumerate(columns):
                with column:
                    if item_products and col_index < len(item_products):
                        render_product_card_item(
                            item_products[col_index],
                            budget_per_item=budget_per_item,
                            index=col_index,
                            key_prefix=f"{key_prefix}_{item_index}",
                        )
                    elif show_placeholders:
                        render_product_card_placeholder(index=col_index, keyword=text[:16])

            search_kw = text if len(text) <= 30 else text[:30]
            kw_label = search_kw[:10] + "…" if len(search_kw) > 10 else search_kw
            st.link_button(
                f"淘宝搜「{kw_label}」",
                _fallback_search_url(search_kw),
                key=f"search_{key_prefix}_{item_index}",
            )

    if not compact:
        st.caption("每个单品最多 5 个推荐 · 点击购买跳转淘宝")
