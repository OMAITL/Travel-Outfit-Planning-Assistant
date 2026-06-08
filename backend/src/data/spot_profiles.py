"""Standardized scenic-spot metadata for AI travel planning."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SpotType = Literal["outdoor", "indoor", "mixed", "urban", "nature", "beach", "temple"]
BestTime = Literal["morning", "afternoon", "evening", "any"]


class SpotProfile(BaseModel):
    id: str
    name: str
    city_key: str
    lat: float
    lng: float
    region: str = Field(description="Macro area for geographic clustering, e.g. 古城片区")
    duration_hours: float = Field(ge=0.5, le=10, description="Recommended visit duration")
    opening_hours: str = "09:00-18:00"
    spot_type: SpotType = "outdoor"
    best_time: BestTime = "any"
    sunrise: bool = False
    sunset: bool = False
    rain_ok: bool = Field(default=True, description="Still enjoyable in rain")
    photo: bool = False
    popularity: int = Field(ge=1, le=5, default=3, description="1=niche, 5=must-see")


class CityAnchor(BaseModel):
    """Default hotel / city-center anchor for distance scoring."""

    city_key: str
    name: str
    lat: float
    lng: float


CITY_ANCHORS: dict[str, CityAnchor] = {
    "dali": CityAnchor(city_key="dali", name="大理", lat=25.6942, lng=100.1642),
    "lijiang": CityAnchor(city_key="lijiang", name="丽江", lat=26.8721, lng=100.2299),
    "chengdu": CityAnchor(city_key="chengdu", name="成都", lat=30.6570, lng=104.0650),
    "sanya": CityAnchor(city_key="sanya", name="三亚", lat=18.2528, lng=109.5119),
    "tokyo": CityAnchor(city_key="tokyo", name="东京", lat=35.6762, lng=139.6503),
}


SPOT_PROFILES: dict[str, SpotProfile] = {
    # —— 大理 ——
    "洱海生态廊道": SpotProfile(
        id="erhai",
        name="洱海生态廊道",
        city_key="dali",
        lat=25.7500,
        lng=100.1800,
        region="洱海片区",
        duration_hours=4.0,
        opening_hours="全天",
        spot_type="nature",
        best_time="afternoon",
        sunset=True,
        rain_ok=False,
        photo=True,
        popularity=5,
    ),
    "大理古城": SpotProfile(
        id="gucheng",
        name="大理古城",
        city_key="dali",
        lat=25.6942,
        lng=100.1642,
        region="古城片区",
        duration_hours=3.0,
        opening_hours="全天",
        spot_type="urban",
        best_time="afternoon",
        rain_ok=True,
        photo=True,
        popularity=5,
    ),
    "崇圣寺三塔": SpotProfile(
        id="santa",
        name="崇圣寺三塔",
        city_key="dali",
        lat=25.7030,
        lng=100.1470,
        region="古城片区",
        duration_hours=2.0,
        opening_hours="07:00-19:00",
        spot_type="temple",
        best_time="morning",
        rain_ok=True,
        photo=True,
        popularity=4,
    ),
    "苍山索道": SpotProfile(
        id="cangshan",
        name="苍山索道",
        city_key="dali",
        lat=25.6880,
        lng=100.0800,
        region="苍山片区",
        duration_hours=4.0,
        opening_hours="08:30-17:00",
        spot_type="nature",
        best_time="morning",
        rain_ok=False,
        photo=True,
        popularity=4,
    ),
    "双廊古镇": SpotProfile(
        id="shuanglang",
        name="双廊古镇",
        city_key="dali",
        lat=25.9080,
        lng=100.1950,
        region="洱海片区",
        duration_hours=3.0,
        opening_hours="全天",
        spot_type="urban",
        best_time="afternoon",
        sunset=True,
        rain_ok=False,
        photo=True,
        popularity=4,
    ),
    "喜洲古镇": SpotProfile(
        id="xizhou",
        name="喜洲古镇",
        city_key="dali",
        lat=25.8570,
        lng=100.1280,
        region="洱海片区",
        duration_hours=2.5,
        opening_hours="08:00-18:00",
        spot_type="urban",
        best_time="morning",
        photo=True,
        popularity=3,
    ),
    # —— 丽江 ——
    "丽江古城": SpotProfile(
        id="gucheng_lj",
        name="丽江古城",
        city_key="lijiang",
        lat=26.8721,
        lng=100.2299,
        region="古城片区",
        duration_hours=4.0,
        opening_hours="全天",
        spot_type="urban",
        best_time="evening",
        sunset=True,
        rain_ok=True,
        photo=True,
        popularity=5,
    ),
    "玉龙雪山": SpotProfile(
        id="yulong",
        name="玉龙雪山",
        city_key="lijiang",
        lat=27.0980,
        lng=100.2580,
        region="雪山片区",
        duration_hours=5.0,
        opening_hours="07:00-16:00",
        spot_type="nature",
        best_time="morning",
        rain_ok=False,
        photo=True,
        popularity=5,
    ),
    "拉市海": SpotProfile(
        id="lashi",
        name="拉市海",
        city_key="lijiang",
        lat=26.8500,
        lng=100.1200,
        region="湿地片区",
        duration_hours=3.0,
        opening_hours="08:00-18:00",
        spot_type="nature",
        best_time="afternoon",
        sunrise=True,
        sunset=True,
        rain_ok=False,
        photo=True,
        popularity=3,
    ),
    # —— 成都 ——
    "宽窄巷子": SpotProfile(
        id="kuanzhai",
        name="宽窄巷子",
        city_key="chengdu",
        lat=30.6633,
        lng=104.0552,
        region="市中心",
        duration_hours=2.5,
        opening_hours="全天",
        spot_type="urban",
        best_time="afternoon",
        rain_ok=True,
        photo=True,
        popularity=5,
    ),
    "大熊猫基地": SpotProfile(
        id="panda",
        name="大熊猫基地",
        city_key="chengdu",
        lat=30.7417,
        lng=104.1463,
        region="北郊片区",
        duration_hours=4.0,
        opening_hours="07:30-18:00",
        spot_type="nature",
        best_time="morning",
        rain_ok=False,
        photo=True,
        popularity=5,
    ),
    "大熊猫繁育研究基地": SpotProfile(
        id="panda",
        name="大熊猫繁育研究基地",
        city_key="chengdu",
        lat=30.7417,
        lng=104.1463,
        region="北郊片区",
        duration_hours=4.0,
        opening_hours="07:30-18:00",
        spot_type="nature",
        best_time="morning",
        rain_ok=False,
        photo=True,
        popularity=5,
    ),
    "锦里古街": SpotProfile(
        id="jinli",
        name="锦里古街",
        city_key="chengdu",
        lat=30.6458,
        lng=104.0487,
        region="市中心",
        duration_hours=2.0,
        opening_hours="全天",
        spot_type="urban",
        best_time="evening",
        sunset=True,
        rain_ok=True,
        photo=True,
        popularity=4,
    ),
    # —— 三亚 ——
    "亚龙湾": SpotProfile(
        id="yalong",
        name="亚龙湾",
        city_key="sanya",
        lat=18.2080,
        lng=109.6400,
        region="东海岸",
        duration_hours=4.0,
        opening_hours="全天",
        spot_type="beach",
        best_time="morning",
        rain_ok=False,
        photo=True,
        popularity=5,
    ),
    "天涯海角": SpotProfile(
        id="tianya",
        name="天涯海角",
        city_key="sanya",
        lat=18.3000,
        lng=109.3500,
        region="西海岸",
        duration_hours=2.5,
        opening_hours="07:30-18:00",
        spot_type="beach",
        best_time="afternoon",
        sunset=True,
        rain_ok=False,
        photo=True,
        popularity=4,
    ),
    "蜈支洲岛": SpotProfile(
        id="wuzhizhou",
        name="蜈支洲岛",
        city_key="sanya",
        lat=18.3100,
        lng=109.7600,
        region="海岛片区",
        duration_hours=6.0,
        opening_hours="08:00-17:30",
        spot_type="beach",
        best_time="morning",
        rain_ok=False,
        photo=True,
        popularity=5,
    ),
    # —— 东京 ——
    "涩谷十字路口": SpotProfile(
        id="shibuya",
        name="涩谷十字路口",
        city_key="tokyo",
        lat=35.6595,
        lng=139.7005,
        region="涩谷",
        duration_hours=2.0,
        opening_hours="全天",
        spot_type="urban",
        best_time="afternoon",
        rain_ok=True,
        photo=True,
        popularity=5,
    ),
    "浅草寺": SpotProfile(
        id="sensoji",
        name="浅草寺",
        city_key="tokyo",
        lat=35.7148,
        lng=139.7967,
        region="浅草",
        duration_hours=2.5,
        opening_hours="06:00-17:00",
        spot_type="temple",
        best_time="morning",
        rain_ok=True,
        photo=True,
        popularity=5,
    ),
    "东京晴空塔": SpotProfile(
        id="skytree",
        name="东京晴空塔",
        city_key="tokyo",
        lat=35.7101,
        lng=139.8107,
        region="晴空塔",
        duration_hours=2.5,
        opening_hours="08:00-22:00",
        spot_type="mixed",
        best_time="evening",
        sunset=True,
        rain_ok=True,
        photo=True,
        popularity=4,
    ),
}


def _city_key_from_destination(destination: str) -> str | None:
    text = destination.strip()
    for key, anchor in CITY_ANCHORS.items():
        if anchor.name in text or key in text.lower():
            return key
    return None


def get_city_anchor(destination: str) -> CityAnchor | None:
    key = _city_key_from_destination(destination)
    return CITY_ANCHORS.get(key) if key else None


def get_spot_profile(name: str) -> SpotProfile | None:
    cleaned = name.strip()
    if not cleaned:
        return None
    if cleaned in SPOT_PROFILES:
        return SPOT_PROFILES[cleaned]
    for profile in SPOT_PROFILES.values():
        if profile.name in cleaned or cleaned in profile.name:
            return profile
    return None


def resolve_spot_profiles(
    spot_names: list[str],
    *,
    destination: str = "",
) -> list[SpotProfile]:
    """Resolve user-selected spot names to profiles; synthesize minimal fallback."""
    city_key = _city_key_from_destination(destination) or "unknown"
    anchor = get_city_anchor(destination)
    profiles: list[SpotProfile] = []
    seen: set[str] = set()

    for name in spot_names:
        cleaned = name.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        profile = get_spot_profile(cleaned)
        if profile:
            profiles.append(profile)
            continue
        profiles.append(
            SpotProfile(
                id=cleaned,
                name=cleaned,
                city_key=city_key,
                lat=anchor.lat if anchor else 0.0,
                lng=anchor.lng if anchor else 0.0,
                region="未知片区",
                duration_hours=3.0,
                spot_type="mixed",
                popularity=3,
            )
        )
    return profiles


def profiles_as_dicts(profiles: list[SpotProfile]) -> list[dict[str, object]]:
    return [p.model_dump() for p in profiles]
