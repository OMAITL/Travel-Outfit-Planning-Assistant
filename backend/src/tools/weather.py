"""AMap (Gaode) weather forecast tool."""

from __future__ import annotations

from datetime import date, timedelta

import httpx

from src.config import get_settings
from src.graph.state import DailyWeather, WeatherCondition
from src.tools.geocode import resolve_city

AMAP_WEATHER_URL = "https://restapi.amap.com/v3/weather/weatherInfo"
# AMap extensions=all returns at most ~4 days from today.


def _normalize_condition(text: str) -> WeatherCondition | str:
    text = text.strip()
    for member in WeatherCondition:
        if member.value == text:
            return member
    if "雨" in text:
        return WeatherCondition.RAINY
    if "雪" in text:
        return WeatherCondition.SNOWY
    if "晴" in text:
        return WeatherCondition.SUNNY
    if "云" in text:
        return WeatherCondition.CLOUDY
    if "阴" in text:
        return WeatherCondition.OVERCAST
    return text


def _seasonal_estimate(day: date) -> DailyWeather:
    """Fallback when AMap has no forecast row for the trip date (beyond ~4 days)."""
    month = day.month
    if month in (12, 1, 2):
        temp_min, temp_max, condition = 0.0, 8.0, WeatherCondition.OVERCAST
    elif month in (3, 4, 5):
        temp_min, temp_max, condition = 10.0, 22.0, WeatherCondition.CLOUDY
    elif month in (6, 7, 8):
        temp_min, temp_max, condition = 20.0, 32.0, WeatherCondition.SUNNY
    elif month in (9, 10, 11):
        temp_min, temp_max, condition = 12.0, 24.0, WeatherCondition.CLOUDY
    else:
        temp_min, temp_max, condition = 15.0, 25.0, WeatherCondition.CLOUDY
    return DailyWeather(
        date=day,
        temp_min=temp_min,
        temp_max=temp_max,
        condition=condition,
        estimated=True,
    )


def _parse_cast(cast: dict) -> DailyWeather:
    cast_date = date.fromisoformat(cast["date"])
    rain_prob = None
    if cast.get("daypower"):
        try:
            rain_prob = float(str(cast["daypower"]).replace("%", ""))
        except ValueError:
            rain_prob = None
    return DailyWeather(
        date=cast_date,
        temp_min=float(cast["nighttemp"]),
        temp_max=float(cast["daytemp"]),
        condition=_normalize_condition(str(cast.get("dayweather", "多云"))),
        rain_prob=rain_prob,
        estimated=False,
    )


def fetch_daily_weather(city: str, start: date, end: date) -> list[DailyWeather]:
    """
    Fetch daily weather for each date in [start, end].

    Uses AMap live forecast when available (typically today + 3 days).
    Missing dates are filled with seasonal estimates so the UI always has data.
    """
    settings = get_settings()
    if not settings.amap_api_key:
        msg = "AMAP_API_KEY is not configured"
        raise ValueError(msg)

    adcode = resolve_city(city)

    response = httpx.get(
        AMAP_WEATHER_URL,
        params={
            "city": adcode,
            "key": settings.amap_api_key,
            "extensions": "all",
        },
        timeout=10.0,
    )
    response.raise_for_status()
    data = response.json()

    if data.get("status") != "1" or not data.get("forecasts"):
        info = data.get("info", "unknown error")
        msg = f"Failed to fetch weather for '{city}': {info}"
        raise ValueError(msg)

    casts = data["forecasts"][0].get("casts", [])
    api_map: dict[date, DailyWeather] = {}
    for cast in casts:
        parsed = _parse_cast(cast)
        if start <= parsed.date <= end:
            api_map[parsed.date] = parsed

    results: list[DailyWeather] = []
    current = start
    while current <= end:
        if current in api_map:
            results.append(api_map[current])
        else:
            results.append(_seasonal_estimate(current))
        current += timedelta(days=1)

    return results
