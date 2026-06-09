"""Simplify outfit item text for Taobao keyword search."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.utils.enrichment import sanitize_item_text_for_commerce
from src.services.body_profile import BodyProfile

# Longer prefixes first so 米白色 matches before 米/白.
_COLOR_PREFIXES = (
    "米白色",
    "米色",
    "米白",
    "白色",
    "黑色",
    "薄荷绿",
    "浅粉色",
    "浅粉",
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
    "粉",
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


def _color_key_for_prefix(prefix: str) -> str:
    if prefix == "卡其":
        return "卡其"
    if prefix in {"米白色", "米色", "米白", "米"}:
        return "米"
    if prefix in {"白色", "白"}:
        return "白"
    if prefix in {"黑色", "黑"}:
        return "黑"
    if prefix.startswith("蓝"):
        return "蓝"
    if prefix.startswith("绿") or prefix == "薄荷绿":
        return "绿"
    if prefix in {"棕色", "咖色"}:
        return "棕"
    if prefix in {"灰色", "灰"}:
        return "灰"
    if prefix.startswith("粉") or prefix in {"粉色", "浅粉色", "浅粉"}:
        return "粉"
    return prefix[0]


def extract_color_phrases(text: str) -> list[str]:
    """Return concrete color phrases from item text for Taobao keywords (e.g. 浅粉色)."""
    cleaned = re.sub(r"\s+", "", text.strip())
    found: list[str] = []
    for prefix in _COLOR_PREFIXES:
        if prefix in cleaned and prefix not in found:
            found.append(prefix)
    return found


@dataclass(frozen=True)
class ItemMaterial:
    key: str
    aliases: tuple[str, ...]
    conflicts: tuple[str, ...]


_ITEM_MATERIALS: tuple[ItemMaterial, ...] = (
    ItemMaterial(
        "草编",
        ("草编", "编织", "藤编", "纸编"),
        ("防水", "尼龙", "牛津布", "PU皮", "PU", "皮革", "真皮", "皮质"),
    ),
)


def extract_item_materials(text: str) -> list[ItemMaterial]:
    """Return material cues from outfit item text for Taobao result filtering."""
    cleaned = re.sub(r"\s+", "", text.strip())
    found: list[ItemMaterial] = []
    for material in _ITEM_MATERIALS:
        if any(token in cleaned for token in (material.key, *material.aliases)):
            found.append(material)
    return found


def extract_item_colors(text: str) -> list[str]:
    """Return normalized color keys found in outfit item text (e.g. 白, 卡其)."""
    cleaned = re.sub(r"\s+", "", text.strip())
    found: list[str] = []
    for prefix in _COLOR_PREFIXES:
        if prefix in cleaned:
            key = _color_key_for_prefix(prefix)
            if key not in found:
                found.append(key)
    return found


def ensure_keyword_has_item_colors(keyword: str, item_text: str) -> str:
    """Prepend missing color tokens so Taobao search matches the recommended item."""
    phrases = extract_color_phrases(item_text)
    if not phrases:
        return keyword.strip()
    cleaned = keyword.strip()
    missing = [phrase for phrase in phrases if phrase not in cleaned.replace(" ", "")]
    if not missing:
        return cleaned
    return " ".join([*missing, cleaned]).strip()


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
    color_phrases = extract_color_phrases(item_text)
    if color_phrases:
        for phrase in color_phrases:
            if phrase not in core:
                core = f"{phrase}{core}"
    parts.append(core)
    keyword = " ".join(part for part in parts if part)
    return ensure_keyword_has_item_colors(keyword, item_text)[:max_len]
