"""Build Xiaohongshu search queries and filter notes by user avoid rules."""

from __future__ import annotations

import re
from datetime import date

from src.services.body_profile import BodyProfile
from src.tools.justone_xhs import XhsNoteSummary

_HEIGHT_SHORT_CM = 160
_HEIGHT_TALL_CM = 170

# Map UI body-type labels to common XHS search wording.
_BODY_TYPE_ALIASES: dict[str, str] = {
    "梨型": "梨形",
    "梨形": "梨形",
    "苹果型": "苹果型",
    "H型": "H型",
    "h型": "H型",
    "沙漏型": "沙漏型",
    "矩形": "H型",
    "倒三角": "倒三角",
    "三角形": "梨形",
}


def season_hint_for_month(month: int) -> str:
    if month in (3, 4, 5):
        return "春季"
    if month in (6, 7, 8):
        return "夏季"
    if month in (9, 10, 11):
        return "秋季"
    return "冬季"


def gender_search_label(gender: str | None) -> str:
    """Map user gender to natural XHS search wording (女生/男生)."""
    value = (gender or "").strip()
    if value in {"", "不限"}:
        return ""
    if value == "女":
        return "女生"
    if value == "男":
        return "男生"
    return value


def height_search_label(height_cm: float | None) -> str:
    """<160 → 小个子; >170 → 高个子; otherwise omit."""
    if height_cm is None or height_cm <= 0:
        return ""
    if height_cm < _HEIGHT_SHORT_CM:
        return "小个子"
    if height_cm > _HEIGHT_TALL_CM:
        return "高个子"
    return ""


def body_type_search_label(body_type: str | None) -> str:
    value = (body_type or "").strip()
    if not value or value in {"不限", "标准", "无"}:
        return ""
    return _BODY_TYPE_ALIASES.get(value, value)


def style_search_label(style: str | None) -> str:
    if not style:
        return ""
    return style.split("、")[0].split(",")[0].strip()


# Full scenic-spot UI names → how users actually search on 小红书.
_SPOT_SEARCH_ALIASES: dict[str, str] = {
    "洱海生态廊道": "洱海",
    "苍山索道": "苍山",
    "崇圣寺三塔": "崇圣寺三塔",
    "双廊古镇": "双廊",
    "喜洲古镇": "喜洲",
    "大理古城": "大理古城",
    "丽江古城": "丽江古城",
    "拉市海": "拉市海",
    "玉龙雪山": "玉龙雪山",
    "宽窄巷子": "宽窄巷子",
    "大熊猫基地": "熊猫基地",
    "锦里古街": "锦里",
    "亚龙湾": "亚龙湾",
    "天涯海角": "天涯海角",
    "蜈支洲岛": "蜈支洲岛",
    "涩谷十字路口": "涩谷",
    "浅草寺": "浅草寺",
    "东京晴空塔": "晴空塔",
}

_SPOT_SUFFIXES = (
    "生态廊道",
    "旅游度假區",
    "旅游度假区",
    "风景区",
    "景区",
    "索道",
    "古镇",
    "古街",
    "基地",
    "步行街",
)


def spot_search_label(spot: str, destination: str = "") -> str:
    """
    Shorten formal spot names for XHS search.

    Users post「洱海 穿搭」far more often than「洱海生态廊道 穿搭」.
    The full name is still kept in itinerary / UI; only the query uses the alias.
    """
    name = spot.strip()
    if not name:
        return destination.strip()
    if name in _SPOT_SEARCH_ALIASES:
        return _SPOT_SEARCH_ALIASES[name]
    for suffix in _SPOT_SUFFIXES:
        if name.endswith(suffix) and len(name) > len(suffix) + 1:
            shortened = name[: -len(suffix)].strip()
            if len(shortened) >= 2:
                return shortened
    return name


def spot_outfit_keyword(
    spot: str,
    *,
    destination: str = "",
    gender: str | None = None,
    style: str | None = None,
    body_type: str | None = None,
    height_cm: float | None = None,
    weight_kg: float | None = None,
) -> str:
    """
    One XHS query per scenic spot, combining user profile + spot + 穿搭.

    Example: 洱海生态廊道 + 女 + 休闲 + 梨型 + 158cm
             → 「洱海 小个子 女生 梨形 休闲 穿搭」
    """
    parts: list[str] = []
    query_spot = spot_search_label(spot, destination)
    if query_spot:
        parts.append(query_spot)

    height_label = height_search_label(height_cm)
    if height_label:
        parts.append(height_label)

    gender_label = gender_search_label(gender)
    if gender_label:
        parts.append(gender_label)

    body_label = body_type_search_label(body_type)
    profile = BodyProfile(
        height_cm=height_cm,
        weight_kg=weight_kg,
        body_type=body_type,
        gender=gender,
    )
    xhs_body = profile.xhs_body_tokens()
    if xhs_body:
        for token in xhs_body:
            if token not in parts:
                parts.append(token)
    elif body_label:
        parts.append(body_label)

    style_label = style_search_label(style)
    if style_label:
        parts.append(style_label)

    parts.append("穿搭")
    return " ".join(parts)


def build_xhs_search_keywords(
    destination: str,
    *,
    style: str = "休闲",
    spot_names: list[str] | None = None,
    gender: str | None = None,
    body_type: str | None = None,
    height_cm: float | None = None,
    weight_kg: float | None = None,
    trip_date: date | None = None,
    max_keywords: int = 4,
) -> list[str]:
    """Backward-compatible wrapper around OutfitQueryCompiler."""
    from src.graph.state import TripPreferences
    from src.services.outfit_query_compiler import OutfitQueryCompiler

    prefs = TripPreferences(
        style=style or "休闲",
        gender=gender,
        body_type=body_type,
        height_cm=height_cm,
        weight_kg=weight_kg,
    )
    spots = [s.strip() for s in (spot_names or []) if s.strip()]
    compiler = OutfitQueryCompiler()
    rows = compiler.compile_queries_for_spots(
        prefs,
        destination=destination,
        spots=spots,
        trip_date=trip_date,
    )
    keywords = [keyword for keyword, _compiled in rows]
    return keywords[:max_keywords]


_AVOID_PREFIXES = ("不穿", "拒穿", "不要", "避免", "忌", "别穿", "不选")


def avoid_match_tokens(avoid_items: list[str] | None) -> list[str]:
    """Extract title/desc tokens to exclude from XHS results."""
    tokens: list[str] = []
    seen: set[str] = set()
    for item in avoid_items or []:
        text = str(item or "").strip()
        if not text:
            continue
        lowered = text.lower()
        for prefix in _AVOID_PREFIXES:
            if lowered.startswith(prefix):
                text = text[len(prefix) :].strip(" ：:，,")
                break
        for chunk in re.split(r"[、,，/\s]+", text):
            chunk = chunk.strip()
            if len(chunk) >= 2 and chunk not in seen:
                seen.add(chunk)
                tokens.append(chunk)
        if len(text) >= 2 and text not in seen:
            seen.add(text)
            tokens.append(text)

    # Common expansions for preset avoid labels.
    expanded: list[str] = []
    for token in tokens:
        expanded.append(token)
        if "裙" in token:
            expanded.extend(["连衣裙", "半裙", "长裙", "短裙"])
        if "牛仔" in token:
            expanded.extend(["牛仔裤", "牛仔裙", "牛仔外套"])
        if "露背" in token:
            expanded.extend(["露背", "大露背", "吊带露背"])
        if "高跟" in token:
            expanded.extend(["高跟鞋", "细高跟"])
    deduped: list[str] = []
    seen_exp: set[str] = set()
    for token in expanded:
        if token and token not in seen_exp:
            seen_exp.add(token)
            deduped.append(token)
    return deduped


def note_hits_avoid_items(note: XhsNoteSummary, avoid_items: list[str] | None) -> bool:
    """True when note title/desc mentions something the user wants to avoid."""
    tokens = avoid_match_tokens(avoid_items)
    if not tokens:
        return False
    text = f"{note.title} {note.desc}"
    return any(token in text for token in tokens)
