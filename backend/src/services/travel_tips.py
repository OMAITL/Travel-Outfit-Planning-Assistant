"""Weather × scenic-spot cross recommendations for daily travel tips."""

from __future__ import annotations

from src.graph.state import DailyWeather

# Curated scene tags per spot (aligned with frontend city catalog).
_SPOT_TAGS: dict[str, frozenset[str]] = {
    "洱海生态廊道": frozenset({"lakeside", "cycling", "photo", "windy"}),
    "大理古城": frozenset({"urban_culture", "stone_path", "walking", "photo"}),
    "崇圣寺三塔": frozenset({"landmark", "outdoor", "photo", "walking"}),
    "苍山索道": frozenset({"mountain", "uphill_walk", "cold_wind", "sun"}),
    "双廊古镇": frozenset({"lakeside", "slow_pace", "photo"}),
    "喜洲古镇": frozenset({"rural_photo", "walking", "photo"}),
    "丽江古城": frozenset({"urban_culture", "stone_path", "walking", "night"}),
    "玉龙雪山": frozenset({"mountain", "cold", "sun", "uphill_walk"}),
    "拉市海": frozenset({"outdoor_park", "wetland", "sun", "walking"}),
    "宽窄巷子": frozenset({"urban_culture", "stone_path", "walking", "photo"}),
    "大熊猫基地": frozenset({"outdoor_park", "vegetation", "mosquito", "uphill_walk", "sun"}),
    "大熊猫繁育研究基地": frozenset({"outdoor_park", "vegetation", "mosquito", "uphill_walk", "sun"}),
    "锦里古街": frozenset({"urban_culture", "stone_path", "walking", "night"}),
    "亚龙湾": frozenset({"beach", "sun", "sand", "swim"}),
    "天涯海角": frozenset({"beach", "sun", "windy", "photo"}),
    "蜈支洲岛": frozenset({"beach", "sun", "swim", "boat"}),
    "涩谷十字路口": frozenset({"urban_street", "photo", "walking", "crowded"}),
    "浅草寺": frozenset({"temple", "urban_culture", "walking", "photo"}),
    "东京晴空塔": frozenset({"landmark", "urban", "photo", "windy"}),
}


def _condition_text(condition) -> str:
    return condition.value if hasattr(condition, "value") else str(condition)


def _infer_spot_tags(spot_name: str) -> frozenset[str]:
    name = spot_name.strip()
    if not name:
        return frozenset()
    if name in _SPOT_TAGS:
        return _SPOT_TAGS[name]

    tags: set[str] = set()
    if any(k in name for k in ("古城", "古镇", "巷子", "古街", "老街")):
        tags.update({"urban_culture", "stone_path", "walking"})
    if any(k in name for k in ("海", "湖", "湾", "岛", "廊道")):
        tags.update({"lakeside", "windy", "photo"})
    if any(k in name for k in ("山", "索道", "雪山")):
        tags.update({"mountain", "uphill_walk", "cold_wind"})
    if any(k in name for k in ("基地", "公园", "湿地", "生态")):
        tags.update({"outdoor_park", "vegetation", "walking"})
    if any(k in name for k in ("寺", "塔", "街", "十字")):
        tags.update({"landmark", "photo", "walking"})
    if any(k in name for k in ("沙滩", "海滨")):
        tags.update({"beach", "sun"})
    return frozenset(tags)


def _outfit_photo_tip(spot: str, outfit_summary: str | None) -> str | None:
    if not outfit_summary:
        return (
            f"📸 拍照贴士：{spot}背景层次丰富，今日穿搭整洁利落，"
            "可搭配亮色唇妆或小巧配饰提升出片率。"
        )
    text = outfit_summary
    if any(k in text for k in ("海军蓝", "藏青", "蓝白", "条纹")) or (
        "蓝" in text and "白" in text
    ):
        return (
            f"📸 拍照贴士：{spot}青砖灰瓦背景较多，今日推荐的海军蓝/蓝白条纹单品"
            "对比鲜明非常出片，建议涂抹亮色口红提升气色。"
        )
    if "白" in text and any(k in text for k in ("裙", "衬衫", "T恤", "针织")):
        return (
            f"📸 拍照贴士：{spot}适合干净背景街拍，今日白色系单品清爽上镜，"
            "可搭配亮色配饰或唇妆增强层次感。"
        )
    if any(k in text for k in ("红", "粉", "黄", "绿")):
        return (
            f"📸 拍照贴士：{spot}景致色彩丰富，今日穿搭已有亮色点缀，"
            "保持自然表情与侧身构图更易出片。"
        )
    return (
        f"📸 拍照贴士：{spot}适合街拍打卡，今日穿搭配色协调，"
        "可适当提亮妆容或配饰增强画面焦点。"
    )


def _spot_tip_for_tag(
    spot: str,
    tag: str,
    tags: frozenset[str],
    outfit_summary: str | None,
) -> str | None:
    if tag == "stone_path":
        return (
            f"💡 出行路况：{spot}多为复古石板路，长时间步行建议选择软底、"
            "防滑的厚底帆布鞋或乐福鞋。"
        )
    if tag in {"photo", "urban_culture"}:
        return _outfit_photo_tip(spot, outfit_summary)
    if tag == "mosquito":
        return (
            f"🦟 户外防护：{spot}植被茂密，早晚蚊虫较多，建议喷好驱蚊水，"
            "或选择今日推荐的长袖上衣搭配长裤。"
        )
    if tag == "outdoor_park" and "mosquito" not in tags:
        return (
            f"🌳 园区步行：{spot}户外步行距离较长，舒适鞋履与防晒补水同样重要。"
        )
    if tag == "uphill_walk":
        return (
            f"🚶‍♀️ 体能建议：{spot}占地面积大、多上坡路，防晒与步行舒适度优先，"
            "建议带一把轻量遮阳伞，穿缓震运动鞋。"
        )
    if tag == "lakeside":
        return (
            f"💨 湖畔提醒：{spot}湖边风大、紫外线反射强，建议备好防风外套与防晒帽，"
            "裙装或轻薄长裤更便于骑行/步行。"
        )
    if tag == "beach":
        return (
            f"🏖️ 海滨提醒：{spot}沙滩日晒强、湿度大，建议选择速干面料与凉鞋，"
            "备一件轻薄防晒罩衫方便进出室内。"
        )
    if tag == "mountain" or tag == "cold_wind":
        if tag != "mountain":
            return None
        return (
            f"⛰️ 山区提醒：{spot}海拔较高、风大温差大，即使白天晴热也建议带一件"
            "可收纳的防风外套。"
        )
    if tag == "urban_street":
        return (
            f"🚶 都市街拍：{spot}人流密集、步行距离长，舒适平底鞋更重要，"
            "穿搭宜简洁利落，方便随时驻足拍照。"
        )
    if tag == "temple":
        return (
            f"⛩️ 人文参观：{spot}步行参观为主，鞋履宜舒适得体，"
            "配饰不宜过于夸张，尊重当地参观礼仪。"
        )
    if tag == "night":
        return f"🌙 夜间活动：{spot}晚间气温可能回落，随身带一件薄外套更稳妥。"
    return None


def _spot_context_tips(spot_names: list[str], outfit_summary: str | None) -> list[str]:
    tips: list[str] = []
    seen: set[str] = set()

    tag_priority = (
        "stone_path",
        "mosquito",
        "uphill_walk",
        "lakeside",
        "beach",
        "mountain",
        "urban_street",
        "temple",
        "photo",
        "urban_culture",
        "night",
        "windy",
    )

    for spot in spot_names:
        if not spot.strip():
            continue
        tags = _infer_spot_tags(spot)
        emitted_photo = False
        for tag in tag_priority:
            if tag not in tags:
                continue
            if tag in {"photo", "urban_culture"} and emitted_photo:
                continue
            tip = _spot_tip_for_tag(spot, tag, tags, outfit_summary)
            if not tip or tip in seen:
                continue
            if tag in {"photo", "urban_culture"}:
                emitted_photo = True
            seen.add(tip)
            tips.append(tip)
    return tips


def precise_weather_tips(weather: DailyWeather) -> list[str]:
    """Numeric weather thresholds — avoid vague '温差大' / '气温偏高'."""
    tips: list[str] = []
    spread = weather.temp_max - weather.temp_min
    condition = _condition_text(weather.condition)
    rain_prob = weather.rain_prob or 0

    if weather.temp_max >= 30:
        tips.append(
            "☀️ 高温提醒：午间紫外线较强、体感闷热，建议配备墨镜、防晒帽，"
            "并随身携带补充水分。"
        )
    elif weather.temp_max >= 28:
        tips.append(
            f"🌡️ 体感偏热：最高气温约 {weather.temp_max:.0f}°C，"
            "推荐轻薄透气面料，午间注意防晒补水。"
        )

    if weather.temp_min <= 18 and spread >= 10:
        tips.append(
            f"🌡️ 温差提醒：早晚温差达 {spread:.0f}°C，上午10点前及晚上8点后体感较凉，"
            "外搭的轻薄外套不可少。"
        )
    elif spread >= 8 and weather.temp_min <= 20:
        tips.append(
            f"🌡️ 昼夜温差：当日温差 {spread:.0f}°C，建议洋葱式分层，"
            "中午可脱外套、早晚及时添衣。"
        )

    if weather.temp_min <= 8:
        tips.append(
            f"🧥 低温提醒：夜间最低约 {weather.temp_min:.0f}°C，需保暖内搭或厚外套。"
        )
    elif weather.temp_min <= 12:
        tips.append(
            f"🌙 早晚偏凉：最低温约 {weather.temp_min:.0f}°C，建议携带薄外套。"
        )

    if "雨" in condition or rain_prob >= 40:
        tips.append(
            "🌧️ 降雨可能：备轻便雨具或防水外套，路面湿滑请选择防滑鞋。"
        )
    elif "雪" in condition:
        tips.append("❄️ 降雪天气：防滑保暖鞋靴与防水外层必备。")
    elif "晴" in condition and 24 <= weather.temp_max < 30:
        tips.append(
            "☀️ 晴日出行：紫外线较强，墨镜/遮阳帽与防晒补涂别忘记。"
        )

    return tips


def build_daily_travel_tips(
    weather: DailyWeather,
    *,
    spot_names: list[str] | None = None,
    outfit_summary: str | None = None,
    max_tips: int = 6,
) -> list[str]:
    """Combine precise weather tips with per-spot scene tag recommendations."""
    tips: list[str] = []
    seen: set[str] = set()

    for tip in precise_weather_tips(weather):
        if tip not in seen:
            seen.add(tip)
            tips.append(tip)

    for tip in _spot_context_tips(spot_names or [], outfit_summary):
        if tip not in seen:
            seen.add(tip)
            tips.append(tip)

    if not tips:
        condition = _condition_text(weather.condition)
        tips.append(
            f"当日 {weather.temp_min:.0f}–{weather.temp_max:.0f}°C、{condition}，"
            "根据体感与行程灵活增减衣物。"
        )

    return tips[:max_tips]


# Backward-compatible alias used in tests.
def weather_travel_tips(weather: DailyWeather) -> list[str]:
    return build_daily_travel_tips(weather)
