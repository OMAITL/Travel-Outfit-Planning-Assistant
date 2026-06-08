"""Simplify outfit item text for Taobao keyword search."""

from __future__ import annotations

import re

from app.utils.enrichment import sanitize_item_text_for_commerce
from src.services.body_profile import BodyProfile

# Longer prefixes first so 米白色 matches before 米/白.
_COLOR_PREFIXES = (
    "米白色",
    "米白",
    "白色",
    "黑色",
    "薄荷绿",
    "浅蓝色",
    "深蓝色",
    "浅蓝",
    "深蓝",
    "杏色",
    "咖色",
    "棕色",
    "灰色",
    "蓝色",
    "绿色",
    "红色",
    "黄色",
    "紫色",
    "粉色",
    "卡其",
    "奶油",
    "白",
    "黑",
    "蓝",
    "绿",
    "红",
    "黄",
    "灰",
    "棕",
    "杏",
)

# Normalized color key -> title tokens that indicate this color.
_COLOR_ALIASES: dict[str, tuple[str, ...]] = {
    "白": ("白", "米白", "米白色", "奶白", "象牙"),
    "黑": ("黑",),
    "蓝": ("蓝", "藏青", "牛仔"),
    "绿": ("绿", "薄荷", "军绿", "墨绿"),
    "红": ("红", "酒红", "玫红"),
    "黄": ("黄", "姜黄", "杏"),
    "灰": ("灰",),
    "棕": ("棕", "咖", "卡其", "驼", "焦糖"),
    "粉": ("粉", "藕粉"),
    "紫": ("紫",),
    "米": ("米", "米白", "杏"),
    "卡其": ("卡其", "驼"),
}

# When item expects one color, penalize titles containing these without the expected color.
_COLOR_CONFLICTS: dict[str, tuple[str, ...]] = {
    "白": ("黑", "绿", "薄荷", "蓝", "红", "灰", "棕", "咖", "卡其"),
    "黑": ("白", "米白", "薄荷", "粉"),
    "米": ("黑", "绿", "薄荷"),
    "卡其": ("黑", "白", "薄荷", "粉"),
    "棕": ("白", "薄荷", "粉"),
    "蓝": ("黑", "红", "绿", "薄荷"),
    "绿": ("白", "米白", "黑", "红", "粉"),
    "黄": ("白", "米白", "黑", "灰", "蓝", "红", "粉"),
}


def extract_item_colors(text: str) -> list[str]:
    """Return normalized color keys found in outfit item text (e.g. 白, 卡其)."""
    cleaned = re.sub(r"\s+", "", text.strip())
    found: list[str] = []
    for prefix in _COLOR_PREFIXES:
        if prefix in cleaned:
            key = "卡其" if prefix == "卡其" else prefix[0]
            if prefix in {"米白色", "米白", "米"}:
                key = "米"
            elif prefix in {"白色", "白"}:
                key = "白"
            elif prefix in {"黑色", "黑"}:
                key = "黑"
            elif prefix.startswith("蓝"):
                key = "蓝"
            elif prefix.startswith("绿") or prefix == "薄荷绿":
                key = "绿"
            elif prefix in {"棕色", "咖色"}:
                key = "棕"
            elif prefix in {"灰色", "灰"}:
                key = "灰"
            if key not in found:
                found.append(key)
    return found


def simplify_item_for_search(text: str, *, max_len: int = 20) -> str:
    """
    Trim outfit item text for Taobao search while keeping color and core garment type.
    Strips AI image-prompt hints (e.g. 及小腿、系带) that hurt search relevance.
    """
    cleaned = sanitize_item_text_for_commerce(text)
    cleaned = re.sub(r"\s+", "", cleaned.strip())
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len]
    return cleaned or sanitize_item_text_for_commerce(text).strip() or text.strip()


def build_item_search_keyword(
    item_text: str,
    *,
    gender: str | None = None,
    style: str | None = None,
    height_cm: float | None = None,
    weight_kg: float | None = None,
    body_type: str | None = None,
    max_len: int = 50,
) -> str:
    """Build a Taobao query that preserves color, garment keywords, and size hints."""
    core = simplify_item_for_search(item_text, max_len=24)
    profile = BodyProfile(
        height_cm=height_cm,
        weight_kg=weight_kg,
        body_type=body_type,
        gender=gender,
    )
    parts: list[str] = []
    if gender and gender not in {"", "不限"}:
        parts.append(gender)
    for token in profile.commerce_size_keywords():
        if token not in parts:
            parts.append(token)
    if style:
        parts.append(style.split("、")[0].split(",")[0].strip())
    parts.append(core)
    keyword = " ".join(part for part in parts if part)
    return keyword[:max_len]
