"""Tests for weather × spot-scene travel tips."""

from __future__ import annotations

from datetime import date

from src.graph.state import DailyWeather, WeatherCondition
from src.services.travel_tips import build_daily_travel_tips, precise_weather_tips


def _weather(*, tmin: float, tmax: float) -> DailyWeather:
    return DailyWeather(
        date=date(2026, 6, 9),
        temp_min=tmin,
        temp_max=tmax,
        condition=WeatherCondition.SUNNY,
        rain_prob=5,
    )


def test_precise_weather_high_temp_threshold() -> None:
    tips = precise_weather_tips(_weather(tmin=19, tmax=30))
    assert any("30" in tip or "高温" in tip for tip in tips)
    assert any("墨镜" in tip for tip in tips)
    assert not any("气温偏高" in tip for tip in tips)


def test_precise_weather_large_diurnal_spread() -> None:
    tips = precise_weather_tips(_weather(tmin=17, tmax=28))
    assert any("11" in tip and "温差" in tip for tip in tips)
    assert any("10点前" in tip for tip in tips)


def test_kuanzhai_alley_scene_tips() -> None:
    tips = build_daily_travel_tips(
        _weather(tmin=17, tmax=28),
        spot_names=["宽窄巷子"],
        outfit_summary="海军蓝白条纹T恤 + 白色阔腿裤 + 乐福鞋",
    )
    assert any("石板路" in tip for tip in tips)
    assert any("海军蓝" in tip or "蓝白条纹" in tip for tip in tips)
    assert any("11" in tip for tip in tips)


def test_panda_base_scene_tips() -> None:
    tips = build_daily_travel_tips(
        _weather(tmin=19, tmax=30),
        spot_names=["大熊猫基地"],
        outfit_summary="长袖防晒衣 + 米色长裤 + 运动鞋",
    )
    assert any("驱蚊" in tip or "蚊虫" in tip for tip in tips)
    assert any("上坡" in tip or "遮阳伞" in tip for tip in tips)
    assert any("高温" in tip or "紫外线" in tip for tip in tips)
