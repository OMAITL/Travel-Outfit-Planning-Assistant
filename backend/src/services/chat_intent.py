"""Outfit-first chat intent parsing helpers for the Trip agent."""

from __future__ import annotations

import re
from datetime import date

from pydantic import BaseModel, Field

SCENE_TYPES = ("拍照", "通勤", "度假", "徒步", "混合")
SCENE_QUICK_OPTIONS = ("出片拍照", "舒适休闲", "混合风格")
DATE_QUICK_OPTIONS = ("本周末", "下周", "7天内", "自定义日期")
GENDER_QUICK_OPTIONS = ("女", "男", "不限")
SPOT_QUICK_OPTIONS = ("市区闲逛", "暂无，帮我推荐")
SPOT_PICK_ALL_OPTION = "都要"
BUDGET_QUICK_OPTIONS = ("100以内", "200左右", "300左右", "500以上", "不设上限")
BODY_TYPE_QUICK_OPTIONS = ("标准", "微胖", "苹果型", "梨型", "H型", "不限")
HEIGHT_WEIGHT_QUICK_OPTIONS = ("160cm / 50kg", "165cm / 55kg", "170cm / 60kg", "175cm / 70kg")
SKIN_TONE_QUICK_OPTIONS = ("偏白", "自然", "小麦色", "偏深", "不限")
AVOID_QUICK_OPTIONS = ("没有", "不穿裙装", "不要高跟鞋", "避免紧身", "不露腰")

_SCENE_OPTION_TO_TYPE = {
    "出片拍照": "拍照",
    "舒适休闲": "度假",
    "混合风格": "混合",
    "拍照": "拍照",
    "通勤": "通勤",
    "度假": "度假",
    "徒步": "徒步",
    "混合": "混合",
    "休闲": "度假",
    "出片": "拍照",
}

_CITY_RECOMMENDED_SPOTS: dict[str, tuple[str, ...]] = {
    "广州": ("沙面岛", "东山口", "广州塔"),
    "大理": ("洱海生态廊道", "大理古城", "喜洲古镇"),
    "北京": ("故宫", "颐和园", "三里屯"),
    "上海": ("外滩", "武康路", "迪士尼"),
    "成都": ("宽窄巷子", "春熙路", "都江堰"),
}

_HEIGHT_WEIGHT_RE = re.compile(
    r"(\d{2,3})\s*(?:cm|厘米)?\s*[/、,，]\s*(\d{2,3})\s*(?:kg|公斤)?",
    re.IGNORECASE,
)

_BUDGET_OPTION_TO_PER_ITEM: dict[str, float] = {
    "100以内": 100.0,
    "200左右": 200.0,
    "300左右": 300.0,
    "500以上": 500.0,
    "不设上限": 9999.0,
}

_SCENE_TO_ACTIVITIES: dict[str, list[str]] = {
    "拍照": ["拍照", "观光"],
    "通勤": ["通勤"],
    "度假": ["度假", "休闲"],
    "徒步": ["徒步", "观光"],
    "混合": ["拍照", "休闲"],
}


class ChatIntentDraft(BaseModel):
    """Partial outfit-first intent while the user is still in chat collection."""

    destination: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    scene_type: str | None = None
    style_tendency: str = ""
    climate_hint: str = ""
    gender: str | None = None
    spot_names: list[str] = Field(default_factory=list)
    budget_per_item: float | None = None
    budget_total: float | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    body_type: str | None = None
    skin_tone: str | None = None
    avoid_items: list[str] = Field(default_factory=list)
    avoid_items_acknowledged: bool = False
    awaiting_spot_pick: bool = False
    missing_fields: list[str] = Field(default_factory=list)


class TripIntentFields(BaseModel):
    """Normalized fields used to decide whether chat collection can finish."""

    destination: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    scene_type: str | None = None
    style_tendency: str = ""
    climate_hint: str = ""
    gender: str | None = None
    spot_names: list[str] = Field(default_factory=list)
    budget_per_item: float | None = None
    budget_total: float | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    body_type: str | None = None
    skin_tone: str | None = None
    avoid_items: list[str] = Field(default_factory=list)
    avoid_items_acknowledged: bool = False
    awaiting_spot_pick: bool = False
    activities: list[str] = Field(default_factory=list)
    style: str = "休闲"
    is_complete: bool = False
    follow_up_question: str | None = None
    follow_up_field: str | None = None
    follow_up_options: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)


def normalize_scene_type(raw: str | None, activities: list[str] | None = None) -> str | None:
    if raw:
        text = raw.strip()
        if text in _SCENE_OPTION_TO_TYPE:
            return _SCENE_OPTION_TO_TYPE[text]
        if text in SCENE_TYPES:
            return text
    if activities:
        joined = " ".join(activities)
        if "拍照" in joined or "出片" in joined:
            return "拍照"
        if "徒步" in joined or "登山" in joined:
            return "徒步"
        if "通勤" in joined:
            return "通勤"
        if "度假" in joined or "休闲" in joined:
            return "度假"
    return None


def normalize_budget_option(raw: str | None, budget_per_item: float | None) -> float | None:
    if budget_per_item is not None:
        return budget_per_item
    if raw:
        text = raw.strip()
        if text in _BUDGET_OPTION_TO_PER_ITEM:
            return _BUDGET_OPTION_TO_PER_ITEM[text]
    return None


def default_recommended_spots(destination: str | None) -> list[str]:
    if not destination:
        return ["经典打卡点"]
    city = destination.strip()
    for key, spots in _CITY_RECOMMENDED_SPOTS.items():
        if key in city or city in key:
            return list(spots)
    return [f"{city}经典景点"]


def normalize_spot_names(raw: list[str] | None, *, destination: str | None) -> list[str]:
    names: list[str] = []
    for part in raw or []:
        text = part.strip()
        if not text:
            continue
        if text == "市区闲逛":
            names.append("市区闲逛")
        else:
            names.append(text)
    return names


def spot_recommendation_follow_up(destination: str | None) -> tuple[str, list[str]]:
    dest = destination or "目的地"
    rec = default_recommended_spots(destination)
    return (
        f"这几个地方在{dest}比较适合拍照，你想去哪些？点选就好～",
        [*rec, SPOT_PICK_ALL_OPTION],
    )


def scene_activities(scene_type: str | None) -> list[str]:
    if not scene_type:
        return []
    return list(_SCENE_TO_ACTIVITIES.get(scene_type, []))


def _core_fields_complete(
    *,
    destination: str | None,
    start_date: date | None,
    end_date: date | None,
    scene: str | None,
) -> bool:
    return bool(destination and start_date and end_date and scene)


def _profile_missing_fields(
    *,
    gender: str | None,
    spot_names: list[str],
    budget_per_item: float | None,
    budget_total: float | None,
    height_cm: float | None,
    weight_kg: float | None,
    body_type: str | None,
    skin_tone: str | None,
    avoid_items_acknowledged: bool,
    require_budget: bool = True,
) -> list[str]:
    missing: list[str] = []
    if not (gender and gender.strip()):
        missing.append("gender")
    if not spot_names:
        missing.append("spot_names")
    if require_budget and budget_per_item is None and budget_total is None:
        missing.append("budget")
    if not (body_type and body_type.strip()):
        missing.append("body_type")
    if height_cm is None or weight_kg is None:
        missing.append("height_weight")
    if not (skin_tone and skin_tone.strip()):
        missing.append("skin_tone")
    if not avoid_items_acknowledged:
        missing.append("avoid_items")
    return missing


def _next_missing_field(missing: list[str]) -> str:
    priority = (
        "destination",
        "dates",
        "start_date",
        "end_date",
        "scene_type",
        "gender",
        "spot_names",
        "budget",
        "body_type",
        "height_weight",
        "skin_tone",
        "avoid_items",
    )
    for field in priority:
        if field in missing:
            return field
        if field == "dates" and ("start_date" in missing or "end_date" in missing):
            return "dates"
    return missing[0] if missing else ""


def build_intent_draft(fields: TripIntentFields) -> ChatIntentDraft:
    return ChatIntentDraft(
        destination=fields.destination,
        start_date=fields.start_date,
        end_date=fields.end_date,
        scene_type=fields.scene_type,
        style_tendency=fields.style_tendency or fields.style,
        climate_hint=fields.climate_hint,
        gender=fields.gender,
        spot_names=list(fields.spot_names),
        budget_per_item=fields.budget_per_item,
        budget_total=fields.budget_total,
        height_cm=fields.height_cm,
        weight_kg=fields.weight_kg,
        body_type=fields.body_type,
        skin_tone=fields.skin_tone,
        avoid_items=list(fields.avoid_items),
        avoid_items_acknowledged=fields.avoid_items_acknowledged,
        awaiting_spot_pick=fields.awaiting_spot_pick,
        missing_fields=fields.missing_fields,
    )


def _pick_str(new: str | None, old: str | None) -> str | None:
    if new is not None and str(new).strip():
        return str(new).strip()
    return old


def _pick_list(new: list[str] | None, old: list[str] | None) -> list[str]:
    if new:
        return list(new)
    return list(old or [])


def merge_extraction_with_draft(
    *,
    destination: str | None,
    start_date: date | None,
    end_date: date | None,
    scene_type: str | None,
    style_tendency: str,
    climate_hint: str,
    gender: str | None,
    spot_names: list[str] | None,
    budget_per_item: float | None,
    budget_total: float | None,
    height_cm: float | None,
    weight_kg: float | None,
    body_type: str | None,
    skin_tone: str | None,
    avoid_items: list[str] | None,
    avoid_items_acknowledged: bool,
    activities: list[str],
    style: str,
    draft: ChatIntentDraft | None,
) -> dict[str, object]:
    """Keep fields collected in earlier chat turns when the LLM returns null."""
    if draft is None:
        return {
            "destination": destination,
            "start_date": start_date,
            "end_date": end_date,
            "scene_type": scene_type,
            "style_tendency": style_tendency,
            "climate_hint": climate_hint,
            "gender": gender,
            "spot_names": spot_names,
            "budget_per_item": budget_per_item,
            "budget_total": budget_total,
            "height_cm": height_cm,
            "weight_kg": weight_kg,
            "body_type": body_type,
            "skin_tone": skin_tone,
            "avoid_items": avoid_items,
            "avoid_items_acknowledged": avoid_items_acknowledged,
            "activities": activities,
            "style": style,
        }

    return {
        "destination": _pick_str(destination, draft.destination),
        "start_date": start_date or draft.start_date,
        "end_date": end_date or draft.end_date,
        "scene_type": _pick_str(scene_type, draft.scene_type),
        "style_tendency": style_tendency or draft.style_tendency,
        "climate_hint": climate_hint or draft.climate_hint,
        "gender": _pick_str(gender, draft.gender),
        "spot_names": _pick_list(spot_names, draft.spot_names),
        "budget_per_item": budget_per_item if budget_per_item is not None else draft.budget_per_item,
        "budget_total": budget_total if budget_total is not None else draft.budget_total,
        "height_cm": height_cm if height_cm is not None else draft.height_cm,
        "weight_kg": weight_kg if weight_kg is not None else draft.weight_kg,
        "body_type": _pick_str(body_type, draft.body_type),
        "skin_tone": _pick_str(skin_tone, draft.skin_tone),
        "avoid_items": _pick_list(avoid_items, draft.avoid_items),
        "avoid_items_acknowledged": avoid_items_acknowledged or draft.avoid_items_acknowledged,
        "activities": activities,
        "style": style or draft.style_tendency or "休闲",
    }


def apply_message_quick_replies(message: str, *, destination: str | None) -> dict[str, object]:
    """Deterministic chip / short-answer parsing — avoids LLM dropping collected fields."""
    text = message.strip()
    if not text:
        return {}

    updates: dict[str, object] = {}

    scene = normalize_scene_type(text)
    if scene:
        updates["scene_type"] = scene

    if text in GENDER_QUICK_OPTIONS:
        updates["gender"] = text

    if text == "市区闲逛":
        updates["spot_names"] = ["市区闲逛"]
        updates["_awaiting_spot_pick"] = False
    elif text in {"暂无，帮我推荐", "帮我推荐"}:
        updates["_awaiting_spot_pick"] = True
    else:
        rec = default_recommended_spots(destination)
        if text == SPOT_PICK_ALL_OPTION:
            updates["spot_names"] = rec
            updates["_awaiting_spot_pick"] = False
        elif text in rec:
            updates["spot_names"] = [text]
            updates["_awaiting_spot_pick"] = False

    if text in BODY_TYPE_QUICK_OPTIONS:
        updates["body_type"] = text

    if text in SKIN_TONE_QUICK_OPTIONS:
        updates["skin_tone"] = text

    if text in BUDGET_QUICK_OPTIONS:
        updates["budget_per_item"] = _BUDGET_OPTION_TO_PER_ITEM[text]

    if text == "没有":
        updates["avoid_items"] = []
        updates["avoid_items_acknowledged"] = True
    elif text in AVOID_QUICK_OPTIONS and text != "没有":
        updates["avoid_items"] = [text]
        updates["avoid_items_acknowledged"] = True

    hw = _HEIGHT_WEIGHT_RE.search(text)
    if hw:
        updates["height_cm"] = float(hw.group(1))
        updates["weight_kg"] = float(hw.group(2))
    elif text in HEIGHT_WEIGHT_QUICK_OPTIONS:
        chip_hw = _HEIGHT_WEIGHT_RE.search(text.replace(" ", ""))
        if chip_hw:
            updates["height_cm"] = float(chip_hw.group(1))
            updates["weight_kg"] = float(chip_hw.group(2))

    return updates


def merge_quick_replies(merged: dict[str, object], quick: dict[str, object]) -> dict[str, object]:
    result = dict(merged)
    for key, value in quick.items():
        if key.startswith("_"):
            result[key] = value
            continue
        if value is None or value == "" or value == []:
            continue
        result[key] = value
    return result


def resolve_awaiting_spot_pick(
    *,
    quick: dict[str, object],
    draft: ChatIntentDraft | None,
) -> bool:
    if quick.get("_awaiting_spot_pick") is True:
        return True
    if quick.get("_awaiting_spot_pick") is False:
        return False
    return bool(draft and draft.awaiting_spot_pick)


def default_follow_up(field: str, *, destination: str | None = None) -> tuple[str, list[str]]:
    dest = destination or "目的地"
    if field == "scene_type":
        return ("这次出行主要是拍照出片，还是轻松逛逛就好？", list(SCENE_QUICK_OPTIONS))
    if field == "dates":
        return ("大概什么时候出发、什么时候回来？", list(DATE_QUICK_OPTIONS))
    if field == "destination":
        return ("打算去哪个城市？告诉我目的地就可以～", [])
    if field == "start_date":
        return ("出发日期是哪天？（例如 7月10日）", list(DATE_QUICK_OPTIONS))
    if field == "end_date":
        return ("返程日期是哪天？", list(DATE_QUICK_OPTIONS))
    if field == "gender":
        return ("为了推荐更合身的搭配，你是女生还是男生？", list(GENDER_QUICK_OPTIONS))
    if field == "spot_names":
        return (
            f"在{dest}有想去的拍照点吗？还没想好可以点「帮我推荐」。",
            list(SPOT_QUICK_OPTIONS),
        )
    if field == "budget":
        return ("单品预算大概多少？我会按预算帮你筛商品。", list(BUDGET_QUICK_OPTIONS))
    if field == "body_type":
        return ("你的体型更偏向哪种？方便我推荐更合适的版型。", list(BODY_TYPE_QUICK_OPTIONS))
    if field == "height_weight":
        return ("身高和体重大概多少？直接告诉我就可以，例如 165cm、55kg。", [])
    if field == "skin_tone":
        return ("你的肤色大概怎样？我会据此搭配更显白的颜色。", [])
    if field == "avoid_items":
        return (
            "有没有特别想避开的单品？比如不穿裙、不要高跟。没有的话直接说「没有」就好。",
            [],
        )
    return (f"再补充一点{dest}的行程信息吧～", [])


def finalize_trip_intent(
    *,
    destination: str | None,
    start_date: date | None,
    end_date: date | None,
    scene_type: str | None,
    style_tendency: str,
    climate_hint: str,
    gender: str | None = None,
    spot_names: list[str] | None = None,
    budget_per_item: float | None = None,
    budget_total: float | None = None,
    height_cm: float | None = None,
    weight_kg: float | None = None,
    body_type: str | None = None,
    skin_tone: str | None = None,
    avoid_items: list[str] | None = None,
    avoid_items_acknowledged: bool = False,
    activities: list[str],
    style: str,
    is_complete: bool,
    follow_up_question: str | None,
    follow_up_field: str | None,
    follow_up_options: list[str],
    budget_hint: str | None = None,
    require_budget: bool = True,
    awaiting_spot_pick: bool = False,
) -> TripIntentFields:
    scene = normalize_scene_type(scene_type, activities)
    spots = normalize_spot_names(spot_names, destination=destination)
    avoid = list(avoid_items or [])
    if avoid == ["没有"]:
        avoid = []
        avoid_items_acknowledged = True
    budget_per_item = normalize_budget_option(budget_hint, budget_per_item)

    missing: list[str] = []
    if not destination:
        missing.append("destination")
    if not start_date:
        missing.append("start_date")
    if not end_date:
        missing.append("end_date")
    if not scene:
        missing.append("scene_type")

    core_complete = _core_fields_complete(
        destination=destination,
        start_date=start_date,
        end_date=end_date,
        scene=scene,
    )

    if core_complete:
        missing.extend(
            _profile_missing_fields(
                gender=gender,
                spot_names=spots,
                budget_per_item=budget_per_item,
                budget_total=budget_total,
                height_cm=height_cm,
                weight_kg=weight_kg,
                body_type=body_type,
                skin_tone=skin_tone,
                avoid_items_acknowledged=avoid_items_acknowledged,
                require_budget=require_budget,
            )
        )

    question = follow_up_question
    options = list(follow_up_options)
    field = follow_up_field

    if missing:
        target = _next_missing_field(missing)
        field = target
        if awaiting_spot_pick and "spot_names" in missing:
            question, options = spot_recommendation_follow_up(destination)
            field = "spot_names"
        else:
            question, options = default_follow_up(target, destination=destination)
        complete = False
    else:
        complete = bool(is_complete)
        if not complete and not question:
            field = "scene_type"
            question, options = default_follow_up("scene_type", destination=destination)

    still_picking_spots = awaiting_spot_pick and not spots

    merged_activities = list(activities)
    for act in scene_activities(scene):
        if act not in merged_activities:
            merged_activities.append(act)

    style_value = style_tendency.strip() or style.strip() or "休闲"
    if scene == "拍照" and "出片" not in style_value:
        style_value = f"{style_value}、出片" if style_value != "休闲" else "休闲出片"

    return TripIntentFields(
        destination=destination,
        start_date=start_date,
        end_date=end_date,
        scene_type=scene,
        style_tendency=style_value,
        climate_hint=climate_hint,
        gender=gender,
        spot_names=spots,
        budget_per_item=budget_per_item,
        budget_total=budget_total,
        height_cm=height_cm,
        weight_kg=weight_kg,
        body_type=body_type,
        skin_tone=skin_tone,
        avoid_items=avoid,
        avoid_items_acknowledged=avoid_items_acknowledged,
        awaiting_spot_pick=still_picking_spots,
        activities=merged_activities,
        style=style_value,
        is_complete=complete,
        follow_up_question=question,
        follow_up_field=field,
        follow_up_options=options,
        missing_fields=missing,
    )
