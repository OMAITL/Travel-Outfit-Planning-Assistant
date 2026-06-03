"""Build natural-language trip messages from structured form fields."""

from __future__ import annotations

from datetime import date


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

    if budget_per_item and budget_per_item > 0:
        segments.append(f"单件预算{int(budget_per_item)}元")
    if budget_total and budget_total > 0:
        segments.append(f"整套穿搭总预算{int(budget_total)}元")

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
ACTIVITY_OPTIONS = ("拍照", "逛街", "徒步", "观光", "美食", "海边", "露营", "商务会议", "亲子")
GENDER_OPTIONS = ("女", "男", "不限")
BODY_TYPE_OPTIONS = ("不限", "苹果型", "梨型", "H型")
SKIN_TONE_OPTIONS = ("不限", "冷白皮", "暖白皮", "自然色", "小麦色", "深肤色")
AVOID_OPTIONS = (
    "不穿裙子",
    "拒穿牛仔",
    "不穿高跟",
    "不穿露脐",
    "不穿紧身",
    "不穿荧光色",
    "不穿黑色",
)

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
