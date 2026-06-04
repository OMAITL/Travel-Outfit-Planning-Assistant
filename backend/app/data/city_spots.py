"""City → scenic spot catalog (from v1 prototype, UI-only)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Spot:
    id: str
    emoji: str
    name: str
    tag: str


@dataclass(frozen=True)
class CityCatalog:
    key: str
    name: str
    spots: tuple[Spot, ...]
    default_spot_ids: tuple[str, ...]


CITY_CATALOG: dict[str, CityCatalog] = {
    "dali": CityCatalog(
        key="dali",
        name="大理",
        spots=(
            Spot("erhai", "🌊", "洱海生态廊道", "拍照 · 骑行"),
            Spot("gucheng", "🏯", "大理古城", "逛街 · 人文"),
            Spot("santa", "🗼", "崇圣寺三塔", "观光 · 出片"),
            Spot("cangshan", "⛰️", "苍山索道", "徒步 · 温差大"),
            Spot("shuanglang", "🏘️", "双廊古镇", "海景 · 慢生活"),
            Spot("xizhou", "🌾", "喜洲古镇", "麦浪 · 拍照"),
        ),
        default_spot_ids=("erhai", "gucheng"),
    ),
    "lijiang": CityCatalog(
        key="lijiang",
        name="丽江",
        spots=(
            Spot("gucheng_lj", "🏯", "丽江古城", "逛街 · 夜景"),
            Spot("yulong", "🏔️", "玉龙雪山", "雪山 · 防寒"),
            Spot("lashi", "🌅", "拉市海", "骑马 · 湿地"),
        ),
        default_spot_ids=("gucheng_lj", "yulong"),
    ),
    "chengdu": CityCatalog(
        key="chengdu",
        name="成都",
        spots=(
            Spot("kuanzhai", "🏮", "宽窄巷子", "逛街 · 美食"),
            Spot("panda", "🐼", "大熊猫基地", "亲子 · 户外"),
            Spot("jinli", "🏯", "锦里古街", "夜景 · 人文"),
        ),
        default_spot_ids=("kuanzhai", "panda"),
    ),
    "sanya": CityCatalog(
        key="sanya",
        name="三亚",
        spots=(
            Spot("yalong", "🏖️", "亚龙湾", "海滩 · 度假"),
            Spot("tianya", "🌅", "天涯海角", "打卡 · 海景"),
            Spot("wuzhizhou", "🤿", "蜈支洲岛", "潜水 · 防晒"),
        ),
        default_spot_ids=("yalong", "tianya"),
    ),
    "tokyo": CityCatalog(
        key="tokyo",
        name="东京",
        spots=(
            Spot("shibuya", "🚶", "涩谷十字路口", "街拍 · 都市"),
            Spot("sensoji", "⛩️", "浅草寺", "人文 · 和服"),
            Spot("skytree", "🗼", "东京晴空塔", "观光 · 夜景"),
        ),
        default_spot_ids=("shibuya", "sensoji"),
    ),
}

CITY_KEYS = list(CITY_CATALOG.keys())


def spot_by_id(spot_id: str) -> Spot | None:
    for city in CITY_CATALOG.values():
        for spot in city.spots:
            if spot.id == spot_id:
                return spot
    return None


def short_spot(name: str) -> str:
    return (
        name.replace("洱海生态廊道", "洱海")
        .replace("大理古城", "古城")
        .replace("崇圣寺三塔", "三塔")
    )
