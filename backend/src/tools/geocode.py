"""AMap (Gaode) geocoding — city name to administrative adcode."""

from __future__ import annotations

import httpx

from src.config import get_settings

AMAP_GEOCODE_URL = "https://restapi.amap.com/v3/geocode/geo"


def resolve_city(city_name: str) -> str:
    """Resolve a city or region name to an AMap adcode for weather queries."""
    settings = get_settings()
    if not settings.amap_api_key:
        msg = "AMAP_API_KEY is not configured"
        raise ValueError(msg)

    response = httpx.get(
        AMAP_GEOCODE_URL,
        params={"address": city_name.strip(), "key": settings.amap_api_key},
        timeout=10.0,
    )
    response.raise_for_status()
    data = response.json()

    if data.get("status") != "1" or not data.get("geocodes"):
        info = data.get("info", "unknown error")
        msg = f"Failed to geocode city '{city_name}': {info}"
        raise ValueError(msg)

    adcode = data["geocodes"][0].get("adcode")
    if not adcode:
        msg = f"No adcode found for city '{city_name}'"
        raise ValueError(msg)
    return adcode
