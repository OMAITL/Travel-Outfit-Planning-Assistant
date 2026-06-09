"""Build Xiaohongshu search queries and filter notes by user avoid rules."""

from __future__ import annotations

import hashlib
import re
from datetime import date
from urllib.parse import quote

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


def build_xhs_search_url(keyword: str) -> str:
    """Deep-link to Xiaohongshu search results for a keyword."""
    cleaned = keyword.strip()
    if not cleaned:
        return "https://www.xiaohongshu.com/explore"
    return f"https://www.xiaohongshu.com/search_result?keyword={quote(cleaned)}"


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


# UI 偏好标签 — 不是小红书搜索高频词，不应直接拼进 query
_PREFERENCE_ONLY_STYLE_TAGS: frozenset[str] = frozenset(
    {
        "拍照出片",
        "舒适优先",
        "户外机能",
        "城市户外",
        "商务休闲",
        "运动休闲",
    }
)

# 偏好标签 → 小红书可搜 synonym（空字符串表示搜索时不加风格词）
_PREFERENCE_STYLE_XHS_MAP: dict[str, str] = {
    "拍照出片": "出片",
    "舒适优先": "",
    "户外机能": "户外",
    "城市户外": "city walk",
}


def pick_xhs_style_for_search(styles: list[str] | None, *, fallback: str = "") -> str:
    """
    Pick the first style token that works on 小红书.

    Skips preference-only tags like「拍照出片」; maps them to searchable synonyms when possible.
    """
    candidates: list[str] = []
    for raw in styles or []:
        candidates.extend(part.strip() for part in raw.replace(",", "、").split("、") if part.strip())
    if not candidates and fallback:
        candidates = [fallback.strip()]

    mapped_fallback = ""
    for tag in candidates:
        if tag in _PREFERENCE_ONLY_STYLE_TAGS:
            mapped = _PREFERENCE_STYLE_XHS_MAP.get(tag, "")
            if mapped and not mapped_fallback:
                mapped_fallback = mapped
            continue
        if tag in _STYLE_EXPANSIONS or len(tag) <= 6:
            return tag
    if mapped_fallback:
        return mapped_fallback
    if fallback and fallback not in _PREFERENCE_ONLY_STYLE_TAGS:
        return fallback.strip()
    return ""


def user_prefers_photogenic(styles: list[str] | None) -> bool:
    return any("拍照出片" in (raw or "") for raw in (styles or []))


# 穿搭搜索同义词 — 一级搜索并行扩展
OUTFIT_QUERY_SUFFIXES: tuple[str, ...] = (
    "穿搭",
    "OOTD",
    "今日穿搭",
    "look",
    "lookbook",
    "街拍",
)

# 景点 → 场景标签（二级搜索降级）
_SPOT_SCENE_MAPPING: dict[str, str] = {
    "洱海": "湖边",
    "西湖": "湖边",
    "宽窄巷子": "古镇",
    "丽江古城": "古城",
    "玉龙雪山": "雪山",
    "蓝月谷": "山水",
    "熊猫基地": "城市公园",
    "大熊猫基地": "城市公园",
    "环球影城": "主题乐园",
    "喜洲": "古镇",
    "双廊": "古镇",
    "大理古城": "古城",
    "锦里": "古镇",
}

# 风格扩展词库 — 搜索时组合以提高召回
_STYLE_EXPANSIONS: dict[str, tuple[str, ...]] = {
    "简约": ("clean fit", "极简穿搭", "韩系通勤"),
    "温柔": ("氛围感穿搭", "奶油色系", "温柔系"),
    "休闲": ("美式休闲", "city walk"),
    "甜美": ("甜妹穿搭", "ins风"),
    "韩系": ("韩系穿搭", "ins风"),
    "海岛风": ("度假穿搭", "海边穿搭"),
    "复古": ("复古穿搭", "vintage"),
    "文艺": ("文艺穿搭", "森系穿搭"),
    "森系": ("森系穿搭", "文艺穿搭"),
    "出片": ("出片穿搭", "氛围感穿搭"),
}

# 非穿搭内容过滤
_NON_OUTFIT_FILTER_HINTS: tuple[str, ...] = (
    "美食攻略",
    "住宿攻略",
    "旅游攻略",
    "打卡攻略",
    "门票攻略",
    "攻略",
    "路线",
    "行程",
    "避雷",
    "美食",
    "探店",
    "门票",
    "住宿",
    "民宿",
    "酒店",
    "交通",
    "自驾",
)

_OUTFIT_POSITIVE_HINTS: tuple[str, ...] = (
    "穿搭",
    "ootd",
    "outfit",
    "搭配",
    "街拍",
    "lookbook",
    "look",
    "拍照穿搭",
    "拍照姿势",
    "出片",
    "衣服",
    "裙",
    "裤",
    "上衣",
    "外套",
    "鞋",
    "造型",
)


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


def spot_scene_label(spot: str, destination: str = "") -> str:
    """Map scenic spot to a scene tag for tier-2 XHS search."""
    label = spot_search_label(spot, destination)
    if label in _SPOT_SCENE_MAPPING:
        return _SPOT_SCENE_MAPPING[label]
    for key, scene in _SPOT_SCENE_MAPPING.items():
        if key in label or label in key:
            return scene
    return ""


def style_expansion_tokens(style: str | None, *, seed: str = "") -> list[str]:
    """Pick 1-2 style expansion tokens (deterministic when seed is set)."""
    base = style_search_label(style)
    if not base:
        return []
    expansions = _STYLE_EXPANSIONS.get(base, ())
    if not expansions:
        return []
    if not seed:
        return [expansions[0]]
    digest = int(hashlib.md5(seed.encode(), usedforsecurity=False).hexdigest(), 16)
    first = expansions[digest % len(expansions)]
    second = expansions[(digest // len(expansions)) % len(expansions)] if len(expansions) > 1 else ""
    tokens = [first]
    if second and second != first:
        tokens.append(second)
    return tokens


def outfit_suffix_variants(*, seed: str = "", limit: int = 4) -> list[str]:
    """Return outfit query suffixes for parallel level-1 search."""
    pool = list(OUTFIT_QUERY_SUFFIXES)
    if not seed or limit >= len(pool):
        return pool[:limit]
    digest = int(hashlib.md5(seed.encode(), usedforsecurity=False).hexdigest(), 16)
    rotated = pool[digest % len(pool) :] + pool[: digest % len(pool)]
    return rotated[:limit]


def note_looks_non_outfit(note: XhsNoteSummary) -> bool:
    """True when note title/desc looks like travel/food guide, not outfit content."""
    text = f"{note.title} {note.desc}".lower()
    if any(cue in text for cue in _OUTFIT_POSITIVE_HINTS):
        return False
    return any(bad in text for bad in _NON_OUTFIT_FILTER_HINTS)


def _profile_body_tokens(
    *,
    height_cm: float | None,
    weight_kg: float | None,
    body_type: str | None,
    gender: str | None,
) -> list[str]:
    """Combine height + XHS-friendly body tokens for search queries."""
    parts: list[str] = []
    height_label = height_search_label(height_cm)
    if height_label:
        parts.append(height_label)
    profile = BodyProfile(
        height_cm=height_cm,
        weight_kg=weight_kg,
        body_type=body_type,
        gender=gender,
    )
    xhs_tokens = profile.xhs_search_body_tokens()
    for token in xhs_tokens:
        if token not in parts:
            parts.append(token)
    if not xhs_tokens:
        body_label = body_type_search_label(body_type)
        if body_label and body_label not in parts and body_label not in {"健壮", "偏瘦"}:
            parts.append(body_label)
    return parts


def build_outfit_search_query(
    *,
    anchor: str,
    gender: str | None = None,
    height_cm: float | None = None,
    weight_kg: float | None = None,
    body_type: str | None = None,
    style: str | None = None,
    suffix: str = "穿搭",
) -> str:
    """Assemble one XHS outfit search string: [anchor] [性别] [身材] [风格] [suffix]."""
    parts: list[str] = []
    anchor = anchor.strip()
    if anchor:
        parts.append(anchor)

    gender_label = gender_search_label(gender)
    if gender_label:
        parts.append(gender_label)

    for token in _profile_body_tokens(
        height_cm=height_cm,
        weight_kg=weight_kg,
        body_type=body_type,
        gender=gender,
    ):
        if token not in parts:
            parts.append(token)

    style_label = style_search_label(style)
    if style_label:
        parts.append(style_label)

    suffix = suffix.strip() or "穿搭"
    parts.append(suffix)
    return " ".join(parts)


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
             → 「洱海 女生 小个子 梨形 休闲 穿搭」
    """
    return build_outfit_search_query(
        anchor=spot_search_label(spot, destination),
        gender=gender,
        height_cm=height_cm,
        weight_kg=weight_kg,
        body_type=body_type,
        style=style,
        suffix="穿搭",
    )


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
