"""Scenic spot descriptions and reference imagery for AI outfit photos."""

from __future__ import annotations

# Curated Wikimedia / stable URLs for prompt conditioning (optional reference)
SPOT_SCENE_CATALOG: dict[str, dict[str, str]] = {
    "洱海生态廊道": {
        "prompt_en": "Erhai Lake ecological corridor, crystal-clear lake, mountain backdrop, cycling path, Yunnan Dali",
        "prompt_zh": "大理洱海生态廊道，湛蓝洱海与苍山背景，网红骑行公路",
    },
    "大理古城": {
        "prompt_en": "Dali ancient town stone streets, traditional Bai architecture, warm afternoon light",
        "prompt_zh": "大理古城青石板路，白族民居，人文街拍背景",
    },
    "崇圣寺三塔": {
        "prompt_en": "Chongsheng Three Pagodas, iconic Buddhist towers, reflective pond, cultural landmark",
        "prompt_zh": "崇圣寺三塔倒影，经典大理地标",
    },
    "苍山索道": {
        "prompt_en": "Cangshan mountain cable car area, alpine forest, dramatic peaks above Dali",
        "prompt_zh": "苍山索道景区，高山云杉与雪峰",
    },
    "双廊古镇": {
        "prompt_en": "Shuanglang ancient town lakeside, boutique guesthouses, Erhai sunset view",
        "prompt_zh": "双廊古镇洱海边，日落海景",
    },
    "喜洲古镇": {
        "prompt_en": "Xizhou ancient town golden wheat fields, white walled courtyard houses",
        "prompt_zh": "喜洲古镇麦浪与白墙灰瓦",
    },
}


def resolve_spot_scene(spot_name: str, destination: str) -> str:
    """Build a detailed scene description for image generation prompts."""
    entry = SPOT_SCENE_CATALOG.get(spot_name)
    if entry:
        return f"{entry['prompt_zh']}（{entry['prompt_en']}）"
    return f"{destination} {spot_name} 真实旅行景点背景，自然光街拍"


def primary_spot_for_day(spot_names: list[str], destination: str) -> str:
    if spot_names:
        return spot_names[0]
    return destination
