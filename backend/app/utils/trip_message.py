"""Build natural-language trip messages from structured form fields."""

from __future__ import annotations

import re
from datetime import date


from src.graph.state import TripContext, TripPreferences, BudgetByCategory
from src.services.budget import normalize_budget_fields


def build_trip_context(
    *,
    destination: str,
    start_date: date,
    end_date: date,
    gender: str | None = None,
    styles: list[str] | None = None,
    activities: list[str] | None = None,
    spot_names: list[str] | None = None,
    plan_mode: str = "auto",
    budget_per_item: float | None = None,
    budget_total: float | None = None,
    budget_by_category: BudgetByCategory | dict[str, float] | None = None,
    party_size: int = 1,
    height_cm: float | None = None,
    weight_kg: float | None = None,
    body_type: str | None = None,
    skin_tone: str | None = None,
    avoid_items: list[str] | None = None,
) -> TripContext:
    """Build a complete TripContext from structured form fields (no LLM)."""
    destination = destination.strip()
    if not destination:
        msg = "destination is required"
        raise ValueError(msg)

    per_item, total, bbc = normalize_budget_fields(
        budget_by_category=budget_by_category,
        budget_per_item=budget_per_item,
        budget_total=budget_total,
    )
    style_text = "、".join(styles) if styles else "休闲"
    return TripContext(
        destination=destination,
        start_date=start_date,
        end_date=end_date,
        preferences=TripPreferences(
            activities=activities or [],
            gender=gender if gender and gender != "不限" else None,
            style=style_text,
            spot_names=spot_names or [],
            plan_mode="manual" if plan_mode == "manual" else "auto",
            budget_per_item=per_item,
            budget_total=total,
            budget_by_category=bbc,
            party_size=party_size,
            height_cm=height_cm,
            weight_kg=weight_kg,
            body_type=body_type if body_type and body_type != "不限" else None,
            skin_tone=skin_tone if skin_tone and skin_tone != "不限" else None,
            avoid_items=avoid_items or [],
        ),
        is_complete=True,
    ).mark_complete()


def build_trip_message(
    *,
    destination: str,
    start_date: date,
    end_date: date,
    gender: str | None = None,
    styles: list[str] | None = None,
    activities: list[str] | None = None,
    budget_per_item: float | None = None,
    budget_total: float | None = None,
    budget_by_category: BudgetByCategory | dict[str, float] | None = None,
    party_size: int = 1,
    height_cm: float | None = None,
    weight_kg: float | None = None,
    body_type: str | None = None,
    skin_tone: str | None = None,
    avoid_items: list[str] | None = None,
) -> str:
    """Compose a trip message the Trip Agent can parse reliably."""
    destination = destination.strip()
    if not destination:
        msg = "destination is required"
        raise ValueError(msg)

    segments: list[str] = [
        f"{start_date.month}月{start_date.day}日到{end_date.month}月{end_date.day}日去{destination}",
    ]

    if party_size > 1:
        segments.append(f"{party_size}人出行")

    if gender and gender != "不限":
        segments.append(gender)

    style_text = "、".join(styles) if styles else "休闲"
    segments.append(f"{style_text}风格")

    if activities:
        segments.append("主要活动：" + "、".join(activities))

    body_parts: list[str] = []
    if height_cm and height_cm > 0:
        body_parts.append(f"身高{int(height_cm)}cm")
    if weight_kg and weight_kg > 0:
        body_parts.append(f"体重{int(weight_kg)}kg")
    if body_type and body_type != "不限":
        body_parts.append(f"{body_type}体型")
    if skin_tone and skin_tone != "不限":
        body_parts.append(f"{skin_tone}肤色")
    if body_parts:
        segments.append("，".join(body_parts))

    if avoid_items:
        segments.append("穿搭避雷：" + "、".join(avoid_items))

    per_item, total, bbc = normalize_budget_fields(
        budget_by_category=budget_by_category,
        budget_per_item=budget_per_item,
        budget_total=budget_total,
    )
    if bbc is not None:
        segments.append(
            "单品预算："
            f"上装{int(bbc.top)}元、下装{int(bbc.bottom)}元、"
            f"鞋{int(bbc.shoes)}元、配饰{int(bbc.acc)}元"
        )
        if total and total > 0:
            segments.append(f"全套合计约{int(total)}元")
    else:
        if per_item and per_item > 0:
            segments.append(f"单件预算{int(per_item)}元")
        if total and total > 0:
            segments.append(f"整套穿搭总预算{int(total)}元")

    return "，".join(segments)


STYLE_OPTIONS = (
    "休闲",
    "韩系",
    "日系",
    "极简",
    "甜美",
    "商务休闲",
    "运动",
    "复古",
    "法式",
    "美式街头",
    "学院风",
    "森系",
    "甜酷",
    "中性风",
    "优雅",
    "度假风",
    "户外机能",
    "新中式",
    "Y2K",
    "暗黑",
    "机车风",
    "通勤",
    "文艺",
    "辣妹",
    "轻奢",
    "工装风",
    "波西米亚",
)
ACTIVITY_OPTIONS = (
    "拍照",
    "逛街",
    "探店",
    "城市漫步",
    "观光",
    "博物馆",
    "古镇游览",
    "美食",
    "夜市",
    "酒吧",
    "海边",
    "潜水",
    "温泉",
    "滑雪",
    "徒步",
    "登山",
    "骑行",
    "露营",
    "自驾游",
    "亲子",
    "约会",
    "闺蜜出游",
    "商务会议",
    "展会论坛",
    "婚礼宴会",
    "演唱会",
    "跑步健身",
    "摄影采风",
    "寺庙参观",
    "农场采摘",
    "沙漠草原",
    "水上运动",
)
GENDER_OPTIONS = ("女", "男", "不限")
BODY_TYPE_OPTIONS = ("不限", "苹果型", "梨型", "H型")
SKIN_TONE_OPTIONS = ("不限", "冷白皮", "暖白皮", "自然色", "小麦色", "深肤色")
AVOID_OPTIONS = (
    "不穿裙子",
    "不穿短裤",
    "拒穿牛仔",
    "不穿高跟",
    "不穿厚底鞋",
    "不穿平底鞋",
    "不穿运动鞋",
    "不穿凉鞋",
    "不穿露脐",
    "不穿露肩",
    "不穿低腰",
    "不穿紧身",
    "不穿透视",
    "不穿荧光色",
    "不穿黑色",
    "不穿白色",
    "不穿浅色",
    "不穿印花",
    "不穿条纹",
    "不穿格子",
    "不穿蕾丝",
    "不穿皮革",
    "不穿连帽衫",
    "不穿西装",
    "不穿polo",
    "不穿毛呢",
    "不穿羊毛",
)


def parse_custom_tags(text: str) -> list[str]:
    """Split free-text tags by common Chinese/Western separators."""
    if not text.strip():
        return []
    parts = re.split(r"[,，、;；|/]+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def merge_avoid_items(selected: list[str], custom_text: str) -> list[str]:
    """Combine preset multiselect values with user-typed avoid items."""
    merged = list(selected)
    for item in parse_custom_tags(custom_text):
        if item not in merged:
            merged.append(item)
    return merged

QUICK_EXAMPLES: dict[str, dict[str, object]] = {
    "大理3日游": {
        "destination": "大理",
        "start_offset": 1,
        "duration": 3,
        "gender": "女",
        "styles": ["休闲", "韩系"],
        "activities": ["拍照", "逛街"],
        "budget_per_item": 200.0,
        "budget_total": 800.0,
        "party_size": 1,
    },
    "北京周末": {
        "destination": "北京",
        "start_offset": 1,
        "duration": 2,
        "gender": "不限",
        "styles": ["商务休闲"],
        "activities": ["观光", "美食"],
        "budget_per_item": 300.0,
        "budget_total": 1200.0,
        "party_size": 2,
    },
    "成都美食行": {
        "destination": "成都",
        "start_offset": 2,
        "duration": 4,
        "gender": "女",
        "styles": ["休闲", "复古"],
        "activities": ["美食", "逛街"],
        "budget_per_item": 150.0,
        "budget_total": 600.0,
        "party_size": 1,
    },
}
