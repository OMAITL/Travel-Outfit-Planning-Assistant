"""Magazine-style product grid — v1 p-card layout."""

from __future__ import annotations

import html
from urllib.parse import quote

import streamlit as st

from app.utils.enrichment import parse_outfit_items
from app.utils.product_grouping import assign_products_to_items
from src.graph.state import DailyOutfit, ProductCard

CATEGORY_LABELS: dict[str, str] = {
    "all": "全部",
    "top": "上装",
    "bottom": "下装",
    "shoes": "鞋",
    "acc": "配饰",
}

LABEL_TO_CAT: dict[str, str] = {
    "上装": "top",
    "外套": "top",
    "内搭": "top",
    "下装": "bottom",
    "鞋": "shoes",
    "配饰": "acc",
    "包": "acc",
    "单品": "all",
    "穿搭": "all",
}


def _label_category(label: str) -> str:
    return LABEL_TO_CAT.get(label, "all")


def _group_products_by_category(
    outfit: DailyOutfit | None,
    products: list[ProductCard],
) -> dict[str, list[ProductCard]]:
    buckets: dict[str, list[ProductCard]] = {key: [] for key in CATEGORY_LABELS}
    seen: set[str] = set()

    groups = assign_products_to_items(outfit, products, max_per_item=5)
    for label, _text, group in groups:
        cat = _label_category(label)
        for product in group:
            pid = product.num_iid or product.detail_url
            if pid in seen:
                continue
            seen.add(pid)
            buckets["all"].append(product)
            if cat != "all":
                buckets[cat].append(product)

    for product in products:
        pid = product.num_iid or product.detail_url
        if pid in seen:
            continue
        buckets["all"].append(product)

    return buckets


def _budget_label(price: float, budget: float | None) -> str:
    if not budget or budget <= 0:
        return "占预算 —"
    ratio = price / budget * 100
    if ratio <= 100:
        return f"占预算 {ratio:.0f}%"
    return f"超预算 {ratio - 100:.0f}%"


def _fallback_search_url(keywords: str) -> str:
    return f"https://s.taobao.com/search?q={quote(keywords)}"


def _render_p_card(
    product: ProductCard,
    *,
    budget_per_item: float | None,
    key_prefix: str,
    index: int,
) -> None:
    title = product.title if len(product.title) <= 36 else f"{product.title[:36]}…"
    budget = _budget_label(product.price, budget_per_item)
    st.markdown(
        f"""
        <div class="p-card">
          <div class="img"><img src="{html.escape(product.pic_url)}" alt="" /></div>
          <div class="body">
            <div class="title">{html.escape(title)}</div>
            <div class="price">¥{product.price:.2f}</div>
            <div class="budget">{html.escape(budget)}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.link_button(
        "去淘宝购买",
        product.detail_url,
        use_container_width=True,
        key=f"pcta_{key_prefix}_{index}_{product.num_iid or index}",
    )


def _render_p_card_placeholder(keyword: str, index: int) -> None:
    st.markdown(
        f"""
        <div class="p-card">
          <div class="img"><span style="font-size:2.2rem">🛍</span></div>
          <div class="body">
            <div class="title">待匹配 · {html.escape(keyword[:14])}</div>
            <div class="price" style="color:#cbd5e1">¥ —</div>
            <div class="budget">OneBound 接入后填充</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_products_magazine(
    outfit: DailyOutfit | None,
    products: list[ProductCard],
    *,
    budget_per_item: float | None = None,
    shopping_errors: list[str] | None = None,
    key_prefix: str = "",
    day_index: int = 0,
) -> None:
    st.markdown(
        """
        <div class="products-head">
          <h4>🛍 推荐商品 — 与穿搭一一对应</h4>
        </div>
        """,
        unsafe_allow_html=True,
    )
    ph, pb = st.columns([3, 1])
    with pb:
        st.markdown('<div class="link-tryon-wrap">', unsafe_allow_html=True)
        if st.button("✨ AI 试衣", key=f"tryon_btn_{key_prefix}", use_container_width=True):
            st.session_state.app_view = "tryon"
            st.session_state.tryon_day_index = day_index
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    if shopping_errors:
        for err in shopping_errors:
            if "OneBound" in err or "onebound" in err.lower():
                st.warning(err)

    buckets = _group_products_by_category(outfit, products)
    categories = [cat for cat in CATEGORY_LABELS if cat == "all" or buckets[cat]]

    filter_key = f"product_cat_{key_prefix}"
    if filter_key not in st.session_state:
        st.session_state[filter_key] = "all"

    st.markdown('<div class="cat-tabs-row">', unsafe_allow_html=True)
    cat_cols = st.columns(len(categories))
    current = st.session_state.get(filter_key, "all")
    for col, cat in zip(cat_cols, categories, strict=True):
        with col:
            if st.button(
                CATEGORY_LABELS[cat],
                key=f"cat_{key_prefix}_{cat}",
                type="primary" if current == cat else "secondary",
                use_container_width=True,
            ):
                st.session_state[filter_key] = cat
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    selected = buckets.get(st.session_state[filter_key], buckets["all"])

    if not selected:
        items = parse_outfit_items(outfit.outfit_summary) if outfit else []
        st.caption("商品接口暂不可用 · 下方为布局预览")
        st.markdown('<div class="product-grid-stream">', unsafe_allow_html=True)
        grid_cols = st.columns(3)
        for index, column in enumerate(grid_cols):
            with column:
                kw = items[index % len(items)][1] if items else "穿搭单品"
                _render_p_card_placeholder(kw[:16], index)
        st.markdown("</div>", unsafe_allow_html=True)
        return

    st.markdown('<div class="product-grid-stream">', unsafe_allow_html=True)
    for row_start in range(0, len(selected), 3):
        cols = st.columns(3)
        for col_index, column in enumerate(cols):
            with column:
                idx = row_start + col_index
                if idx < len(selected):
                    _render_p_card(
                        selected[idx],
                        budget_per_item=budget_per_item,
                        key_prefix=key_prefix,
                        index=idx,
                    )
    st.markdown("</div>", unsafe_allow_html=True)

    if outfit and outfit.search_keywords:
        st.link_button(
            "🔍 在淘宝搜索更多",
            _fallback_search_url(outfit.search_keywords[0]),
            key=f"mag_more_{key_prefix}",
        )
