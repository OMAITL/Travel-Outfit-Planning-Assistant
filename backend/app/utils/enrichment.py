"""Derive display metadata (tips, scores, colors) for the UI layer."""

from __future__ import annotations

import re

from src.graph.state import DailyWeather, TripPreferences
from src.services.travel_tips import build_daily_travel_tips, weather_travel_tips

__all__ = [
    "build_daily_travel_tips",
    "weather_travel_tips",
]

COLOR_KEYWORDS: dict[str, str] = {
    "白": "#f8fafc",
    "黑": "#1e293b",
    "米": "#fef3c7",
    "卡其": "#d4a574",
    "蓝": "#3b82f6",
    "藏青": "#1e3a5f",
    "绿": "#22c55e",
    "军绿": "#4d7c0f",
    "粉": "#f472b6",
    "红": "#ef4444",
    "黄": "#eab308",
    "灰": "#94a3b8",
    "棕": "#92400e",
    "杏": "#fcd34d",
    "紫": "#a855f7",
}


def _condition_text(condition) -> str:
    return condition.value if hasattr(condition, "value") else str(condition)


def weather_outfit_impact(weather: DailyWeather, outfit_summary: str | None = None) -> str:
    """Explain why the outfit fits the weather."""
    condition = _condition_text(weather.condition)
    spread = weather.temp_max - weather.temp_min
    parts = [f"当日 {weather.temp_min:.0f}–{weather.temp_max:.0f}°C、{condition}，"]

    if spread >= 8:
        parts.append("温差较大，分层穿搭便于随时增减；")
    elif weather.temp_max >= 28:
        parts.append("偏热，应以轻薄透气为主；")
    elif weather.temp_min <= 10:
        parts.append("偏凉，需兼顾保暖与活动舒适度；")
    else:
        parts.append("温度适中，兼顾舒适与活动便利；")

    if "雨" in condition:
        parts.append("降雨天气优先防水/quick-dry 材质。")
    elif "晴" in condition:
        parts.append("晴天适合浅色防晒单品，拍照也更出片。")
    else:
        parts.append("根据体感灵活调整外层厚度。")

    if outfit_summary:
        if "防晒" in outfit_summary and "晴" in condition:
            parts.append("方案含防晒单品，与当日天气匹配。")
        if ("雨" in condition or (weather.rain_prob or 0) >= 40) and any(
            k in outfit_summary for k in ("防水", "雨", "冲锋")
        ):
            parts.append("方案考虑防雨需求。")

    return "".join(parts)


def extract_color_palette(text: str, limit: int = 4) -> list[tuple[str, str]]:
    """Extract color chips from outfit description."""
    found: list[tuple[str, str]] = []
    for name, hex_code in COLOR_KEYWORDS.items():
        if name in text and (name, hex_code) not in found:
            found.append((name, hex_code))
        if len(found) >= limit:
            break
    if not found:
        found = [("中性色", "#94a3b8"), ("基础色", "#e2e8f0")]
    return found


def parse_outfit_items(summary: str) -> list[tuple[str, str]]:
    """Split outfit summary into labeled items (supports 上装：XXX | 下装：XXX)."""
    if "|" in summary or "｜" in summary:
        segments = re.split(r"[|｜]", summary)
    elif "+" in summary or "＋" in summary:
        segments = re.split(r"[+＋]", summary)
    else:
        segments = [summary]

    items: list[tuple[str, str]] = []
    label_pattern = re.compile(r"^(上装|下装|鞋|外套|配饰|内搭|包)[：:]\s*(.+)$")

    for segment in segments:
        text = segment.strip().strip("。")
        if not text:
            continue

        match = label_pattern.match(text)
        if match:
            items.append((match.group(1), match.group(2).strip()))
            continue

        label = "单品"
        for keyword, name in (
            ("鞋", "鞋"),
            ("包", "包"),
            ("帽", "配饰"),
            ("裤", "下装"),
            ("裙", "下装"),
            ("外套", "外套"),
            ("衬衫", "上装"),
            ("T恤", "上装"),
            ("上衣", "上装"),
            ("针织", "上装"),
        ):
            if keyword in text:
                label = name
                break
        items.append((label, text))

    return items or [("穿搭", summary)]


_SKIP_ITEM_TEXT = {"", "无", "不需要", "none", "n/a", "-", "—"}

_NON_PURCHASABLE_HINTS = (
    "发型",
    "编发",
    "麻花辫",
    "侧边辫",
    "马尾",
    "丸子头",
    "卷发",
    "直发",
    "刘海",
    "发色",
    "妆容",
    "化妆",
    "口红",
    "眼影",
    "粉底",
    "腮红",
    "拍照姿势",
    "姿势",
    "pose",
    "摆拍",
    "机位",
    "角度",
    "美甲",
    "纹身",
)


def is_purchasable_item_text(text: str) -> bool:
    """True when the outfit slot represents a shoppable garment or accessory."""
    cleaned = text.strip()
    if not cleaned or cleaned.lower() in _SKIP_ITEM_TEXT:
        return False
    return not any(hint in cleaned for hint in _NON_PURCHASABLE_HINTS)


def _split_outside_parens(text: str) -> list[str]:
    """Split on list delimiters only when not inside （） or ()."""
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    delimiters = "、，,;；+/＋|｜"
    for char in text:
        if char in "（(":
            depth += 1
            current.append(char)
        elif char in "）)":
            depth = max(0, depth - 1)
            current.append(char)
        elif char in delimiters and depth == 0:
            segment = "".join(current).strip()
            if segment:
                parts.append(segment)
            current = []
        else:
            current.append(char)
    segment = "".join(current).strip()
    if segment:
        parts.append(segment)
    return parts


def _looks_like_paren_fragment(part: str) -> bool:
    """True when a segment is a broken parenthetical shard, not a real item."""
    stripped = part.strip()
    if not stripped:
        return True
    if stripped.startswith(("（", "(")) and not stripped.endswith(("）", ")")):
        return True
    if stripped.endswith(("）", ")")) and not stripped.startswith(("（", "(")):
        return True
    if len(stripped) <= 4 and stripped in {"短袖", "露脐", "圆领", "系带", "低帮"}:
        return True
    return False


def split_compound_item_text(text: str) -> list[str]:
    """Split accessory lists like 宽檐草帽、民族风耳环、草编手提包 into separate slots."""
    text = text.strip()
    if not text:
        return []

    parts = _split_outside_parens(text)
    cleaned = [part for part in parts if part and part.lower() not in _SKIP_ITEM_TEXT]
    if len(cleaned) <= 1:
        return [text]
    if any(_looks_like_paren_fragment(part) for part in cleaned):
        return [text]
    return cleaned


# Parenthetical / inline phrases for AI image prompts only — strip from UI & Taobao search.
_PROMPT_PAREN_HINTS = (
    "垂坠感",
    "前短后长",
    "设计感",
    "氛围感",
    "质感",
    "显瘦",
    "遮胯",
    "配浅灰袜",
    "菱格纹",
    "金属链",
    # Length & fit cues for image generation — not useful on Taobao
    "及小腿",
    "及膝",
    "及踝",
    "及腰",
    "及大腿",
    "系带",
    "系带收腰",
    "绑带",
    "抽绳",
    "开衩",
    "不规则下摆",
    "层叠",
    "层次感",
)


def _paren_inner_is_prompt_only(inner: str) -> bool:
    """True when parenthetical content is image-prompt metadata, not a product SKU attribute."""
    if any(hint in inner for hint in _PROMPT_PAREN_HINTS):
        return True
    stripped = inner.strip()
    if re.match(r"^及?(小腿|膝|踝|腰|大腿)$", stripped):
        return True
    if re.match(r"^系带(?:收腰)?$", stripped):
        return True
    return False


def sanitize_item_text_for_display(text: str) -> str:
    """Remove AI image-prompt hints; keep purchasable attributes like （圆领短袖）."""

    def _replace(match: re.Match[str]) -> str:
        inner = match.group(1)
        if _paren_inner_is_prompt_only(inner):
            return ""
        return match.group(0)

    result = re.sub(r"（([^）]*)）", _replace, text.strip())
    result = re.sub(r"\(([^)]*)\)", _replace, result)
    return re.sub(r"\s+", " ", result).strip() or text.strip()


def sanitize_item_text_for_commerce(text: str) -> str:
    """Same as display sanitizer — used before Taobao search and product matching."""
    return sanitize_item_text_for_display(text)


def sanitize_recommendation_reason(text: str) -> str:
    """Strip leading Xiaohongshu citation from stylist recommendation_reason."""
    cleaned = text.strip()
    cleaned = re.sub(
        r"^参考小红书[「\"].*?[」\"]\s*高赞笔记[，,]?\s*",
        "",
        cleaned,
    )
    cleaned = re.sub(r"^参考小红书.*?高赞笔记[，,]?\s*", "", cleaned)
    return cleaned.strip() or text.strip()


def expand_outfit_item_slots(items: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Expand compound item descriptions into one slot per purchasable piece."""
    expanded: list[tuple[str, str]] = []
    for label, text in items:
        if not is_purchasable_item_text(text):
            continue
        sub_items = split_compound_item_text(text)
        if len(sub_items) <= 1:
            expanded.append((label, text))
            continue
        for sub in sub_items:
            if is_purchasable_item_text(sub):
                expanded.append((label, sub))
    return expanded


def derive_outfit_scores(
    outfit_summary: str,
    preferences: TripPreferences | None = None,
) -> dict[str, int]:
    """Heuristic 1–5 scores for style, comfort, and photo-readiness."""
    style = preferences.style if preferences else "休闲"
    activities = preferences.activities if preferences else []

    comfort = 4
    photo = 3
    style_match = 4

    breathable = ("棉", "麻", "透气", "运动", "休闲")
    if any(k in outfit_summary for k in breathable):
        comfort += 1
    if any(k in outfit_summary for k in ("高跟", "硬底", "紧身")):
        comfort -= 1

    photo_kw = ("拍照", "出片", "色彩", "层次", "防晒衫", "裙", "帽", "墨镜")
    if any(k in outfit_summary for k in photo_kw):
        photo += 1
    if "拍照" in activities or "海边" in activities:
        photo += 1
    if style in outfit_summary or style in " ".join(activities):
        style_match += 1

    def clamp(value: int) -> int:
        return max(1, min(5, value))

    return {
        "style": clamp(style_match),
        "comfort": clamp(comfort),
        "photo": clamp(photo),
    }


def score_stars(value: int) -> str:
    return "★" * value + "☆" * (5 - value)
