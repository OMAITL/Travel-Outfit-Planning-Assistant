"""Score and rank candidate travel routes."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from src.data.spot_profiles import CityAnchor, SpotProfile
from src.graph.state import DailyWeather
from src.services.itinerary_rules import (
    DayPlanDraft,
    RouteDraft,
    _is_rainy,
    _is_sunny,
    _weather_fit_score,
    haversine_km,
)


class RouteScoreBreakdown(BaseModel):
    distance: float = 0.0
    weather: float = 0.0
    popularity: float = 0.0
    preference: float = 0.0
    photo: float = 0.0
    total: float = 0.0


class ScoredRoute(BaseModel):
    route: RouteDraft
    breakdown: RouteScoreBreakdown


WEIGHTS = {
    "distance": 0.25,
    "weather": 0.25,
    "popularity": 0.15,
    "preference": 0.20,
    "photo": 0.15,
}


def _day_travel_km(spots: list[str], profiles: dict[str, SpotProfile], anchor: CityAnchor | None) -> float:
    if not spots:
        return 0.0
    coords = [profiles[s] for s in spots if s in profiles]
    if not coords:
        return 0.0
    total = 0.0
    if anchor:
        total += haversine_km(anchor.lat, anchor.lng, coords[0].lat, coords[0].lng)
    for i in range(1, len(coords)):
        total += haversine_km(coords[i - 1].lat, coords[i - 1].lng, coords[i].lat, coords[i].lng)
    return total


def _score_distance(route: RouteDraft, profiles: dict[str, SpotProfile], anchor: CityAnchor | None) -> float:
    kms = [_day_travel_km(day.spots, profiles, anchor) for day in route.days]
    if not kms:
        return 0.5
    avg = sum(kms) / len(kms)
    # 0 km → 1.0 ; 40+ km/day → ~0.2
    return max(0.0, min(1.0, 1.0 - avg / 50.0))


def _score_weather(
    route: RouteDraft,
    profiles: dict[str, SpotProfile],
    weather_by_date: dict[date, DailyWeather],
) -> float:
    scores: list[float] = []
    for day in route.days:
        weather = weather_by_date.get(day.date)
        if not day.spots:
            scores.append(0.5)
            continue
        day_scores = [_weather_fit_score(profiles[s], weather) for s in day.spots if s in profiles]
        scores.append(sum(day_scores) / len(day_scores) if day_scores else 0.5)
    return sum(scores) / len(scores) if scores else 0.5


def _score_popularity(route: RouteDraft, profiles: dict[str, SpotProfile]) -> float:
    spots = [s for day in route.days for s in day.spots]
    if not spots:
        return 0.0
    vals = [profiles[s].popularity / 5.0 for s in spots if s in profiles]
    return sum(vals) / len(vals) if vals else 0.5


def _score_preference(
    route: RouteDraft,
    profiles: dict[str, SpotProfile],
    preferences: dict[str, object] | None,
) -> float:
    if not preferences:
        return 0.7
    activities = [str(a) for a in preferences.get("activities", [])]
    style = str(preferences.get("style", ""))
    scores: list[float] = []
    for day in route.days:
        for spot in day.spots:
            profile = profiles.get(spot)
            if not profile:
                scores.append(0.5)
                continue
            fit = 0.7
            if any(k in activities for k in ("拍照", "摄影", "出片")) and profile.photo:
                fit += 0.2
            if any(k in activities for k in ("逛街", "美食", "人文")) and profile.spot_type in {"urban", "temple"}:
                fit += 0.1
            if "休闲" in style and profile.spot_type in {"urban", "beach"}:
                fit += 0.05
            scores.append(min(1.0, fit))
    return sum(scores) / len(scores) if scores else 0.7


def _score_photo(
    route: RouteDraft,
    profiles: dict[str, SpotProfile],
    weather_by_date: dict[date, DailyWeather],
) -> float:
    scores: list[float] = []
    for day in route.days:
        weather = weather_by_date.get(day.date)
        sunny = _is_sunny(weather)
        rainy = _is_rainy(weather)
        photo_spots = [s for s in day.spots if s in profiles and profiles[s].photo]
        if not photo_spots:
            scores.append(0.5)
            continue
        day_score = 0.0
        for spot in photo_spots:
            profile = profiles[spot]
            pts = 0.6
            if sunny and profile.spot_type in {"nature", "beach", "urban"}:
                pts += 0.25
            if profile.sunset and (profile.best_time == "evening" or profile.sunset):
                pts += 0.15
            if rainy and not profile.rain_ok:
                pts -= 0.3
            day_score += max(0.0, min(1.0, pts))
        scores.append(day_score / len(photo_spots))
    return sum(scores) / len(scores) if scores else 0.5


def score_route(
    route: RouteDraft,
    *,
    profiles: dict[str, SpotProfile],
    weather_by_date: dict[date, DailyWeather],
    preferences: dict[str, object] | None = None,
    anchor: CityAnchor | None = None,
) -> RouteScoreBreakdown:
    distance = _score_distance(route, profiles, anchor)
    weather = _score_weather(route, profiles, weather_by_date)
    popularity = _score_popularity(route, profiles)
    preference = _score_preference(route, profiles, preferences)
    photo = _score_photo(route, profiles, weather_by_date)
    total = (
        distance * WEIGHTS["distance"]
        + weather * WEIGHTS["weather"]
        + popularity * WEIGHTS["popularity"]
        + preference * WEIGHTS["preference"]
        + photo * WEIGHTS["photo"]
    )
    return RouteScoreBreakdown(
        distance=round(distance, 3),
        weather=round(weather, 3),
        popularity=round(popularity, 3),
        preference=round(preference, 3),
        photo=round(photo, 3),
        total=round(total, 3),
    )


def pick_best_route(
    routes: list[RouteDraft],
    *,
    profiles: dict[str, SpotProfile],
    weather_by_date: dict[date, DailyWeather],
    preferences: dict[str, object] | None = None,
    anchor: CityAnchor | None = None,
) -> ScoredRoute:
    best: ScoredRoute | None = None
    for route in routes:
        breakdown = score_route(
            route,
            profiles=profiles,
            weather_by_date=weather_by_date,
            preferences=preferences,
            anchor=anchor,
        )
        scored = ScoredRoute(route=route, breakdown=breakdown)
        if best is None or scored.breakdown.total > best.breakdown.total:
            best = scored
    if best is None:
        empty = RouteDraft(name="Route A", days=[])
        return ScoredRoute(route=empty, breakdown=RouteScoreBreakdown())
    return best
