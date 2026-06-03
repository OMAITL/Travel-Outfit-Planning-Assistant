from datetime import date
from unittest.mock import patch

import httpx
import pytest
from pydantic import ValidationError

from src.config import Settings
from src.graph.state import WeatherCondition
from src.tools.geocode import resolve_city
from src.tools.weather import fetch_daily_weather

GEOCODE_URL = "https://restapi.amap.com/v3/geocode/geo"
WEATHER_URL = "https://restapi.amap.com/v3/weather/weatherInfo"


GEOCODE_RESPONSE = {
    "status": "1",
    "info": "OK",
    "geocodes": [{"adcode": "110000", "formatted_address": "北京市"}],
}

WEATHER_RESPONSE = {
    "status": "1",
    "info": "OK",
    "forecasts": [
        {
            "city": "北京市",
            "adcode": "110000",
            "casts": [
                {
                    "date": "2026-06-03",
                    "dayweather": "晴",
                    "nightweather": "晴",
                    "daytemp": "29",
                    "nighttemp": "17",
                },
                {
                    "date": "2026-06-04",
                    "dayweather": "小雨",
                    "nightweather": "阴",
                    "daytemp": "26",
                    "nighttemp": "15",
                },
            ],
        }
    ],
}


def test_validate_amap_raises_when_missing() -> None:
    settings = Settings(_env_file=None, amap_api_key=None)
    with pytest.raises(ValidationError):
        settings.validate_amap()


def _json_response(url: str, data: dict) -> httpx.Response:
    request = httpx.Request("GET", url)
    return httpx.Response(200, json=data, request=request)


def test_resolve_city_returns_adcode() -> None:
    mock_response = _json_response(GEOCODE_URL, GEOCODE_RESPONSE)
    with patch("src.tools.geocode.httpx.get", return_value=mock_response):
        assert resolve_city("北京") == "110000"


def test_resolve_city_raises_on_api_error() -> None:
    mock_response = _json_response(GEOCODE_URL, {"status": "0", "info": "INVALID_USER_KEY"})
    with patch("src.tools.geocode.httpx.get", return_value=mock_response):
        with pytest.raises(ValueError, match="Failed to geocode"):
            resolve_city("北京")


def test_fetch_daily_weather_filters_by_date_range() -> None:
    geocode_resp = _json_response(GEOCODE_URL, GEOCODE_RESPONSE)
    weather_resp = _json_response(WEATHER_URL, WEATHER_RESPONSE)

    def mock_get(url: str, **kwargs: object) -> httpx.Response:
        if "geocode" in url:
            return geocode_resp
        return weather_resp

    with patch("src.tools.geocode.httpx.get", side_effect=mock_get):
        with patch("src.tools.weather.httpx.get", side_effect=mock_get):
            results = fetch_daily_weather(
                "北京",
                start=date(2026, 6, 3),
                end=date(2026, 6, 3),
            )

    assert len(results) == 1
    assert results[0].date == date(2026, 6, 3)
    assert results[0].temp_min == 17.0
    assert results[0].temp_max == 29.0
    assert results[0].condition == WeatherCondition.SUNNY


def test_fetch_daily_weather_fills_missing_dates_with_estimates() -> None:
    geocode_resp = _json_response(GEOCODE_URL, GEOCODE_RESPONSE)
    weather_resp = _json_response(WEATHER_URL, WEATHER_RESPONSE)

    def mock_get(url: str, **kwargs: object) -> httpx.Response:
        if "geocode" in url:
            return geocode_resp
        return weather_resp

    with patch("src.tools.geocode.httpx.get", side_effect=mock_get):
        with patch("src.tools.weather.httpx.get", side_effect=mock_get):
            results = fetch_daily_weather(
                "北京",
                start=date(2026, 6, 3),
                end=date(2026, 6, 5),
            )

    assert len(results) == 3
    assert results[0].estimated is False
    assert results[1].estimated is False
    assert results[2].estimated is True
    assert results[2].date == date(2026, 6, 5)


def test_fetch_daily_weather_normalizes_rainy_condition() -> None:
    geocode_resp = _json_response(GEOCODE_URL, GEOCODE_RESPONSE)
    weather_resp = _json_response(WEATHER_URL, WEATHER_RESPONSE)

    def mock_get(url: str, **kwargs: object) -> httpx.Response:
        if "geocode" in url:
            return geocode_resp
        return weather_resp

    with patch("src.tools.geocode.httpx.get", side_effect=mock_get):
        with patch("src.tools.weather.httpx.get", side_effect=mock_get):
            results = fetch_daily_weather(
                "北京",
                start=date(2026, 6, 4),
                end=date(2026, 6, 4),
            )

    assert results[0].condition == WeatherCondition.RAINY
