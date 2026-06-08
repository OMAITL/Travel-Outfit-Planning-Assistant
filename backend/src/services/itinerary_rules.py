"""Rule-based travel planner — geographic clustering, duration & weather constraints."""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from src.data.spot_profiles import SpotProfile, get_city_anchor, resolve_spot_profiles
from src.graph.state import DailyWeather, DayItinerary, WeatherCondition

MIN_HOURS_PER_DAY = 4.0
MAX_HOURS_PER_DAY = 8.0
TARGET_HOURS_PER_DAY = 7.0

PlanningMode = Literal["equal", "pack", "spread"]


class DayPlanDraft(BaseModel):
    date: date
    spots: list[str] = Field(default_factory=list)
    reason: str = ""
    use_time_slots: bool = Field(
        default=True,
        description="False when a single full-day spot needs no AM/PM/evening split",
    )


class RouteDraft(BaseModel):
    name: str
    days: list[DayPlanDraft] = Field(default_factory=list)


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _profile_map(profiles: list[SpotProfile]) -> dict[str, SpotProfile]:
    return {p.name: p for p in profiles}


def _planning_mode(n_spots: int, n_days: int) -> PlanningMode:
    if n_spots == n_days:
        return "equal"
    if n_spots > n_days:
        return "pack"
    return "spread"


def _is_rainy(weather: DailyWeather | None) -> bool:
    if weather is None:
        return False
    condition = weather.condition.value if hasattr(weather.condition, "value") else str(weather.condition)
    return "雨" in condition or (weather.rain_prob or 0) >= 50


def _is_sunny(weather: DailyWeather | None) -> bool:
    if weather is None:
        return True
    condition = weather.condition.value if hasattr(weather.condition, "value") else str(weather.condition)
    if isinstance(weather.condition, WeatherCondition):
        return weather.condition in {WeatherCondition.SUNNY, WeatherCondition.CLOUDY}
    return "晴" in condition or "云" in condition


def _weather_fit_score(profile: SpotProfile, weather: DailyWeather | None) -> float:
    rainy = _is_rainy(weather)
    sunny = _is_sunny(weather)
    if rainy:
        if profile.rain_ok or profile.spot_type in {"indoor", "urban", "mixed", "temple"}:
            return 1.0
        return 0.2
    if sunny and profile.spot_type in {"nature", "beach", "outdoor"}:
        return 1.0
    if sunny:
        return 0.85
    return 0.7


def _cluster_by_region(profiles: list[SpotProfile]) -> list[list[SpotProfile]]:
    buckets: dict[str, list[SpotProfile]] = defaultdict(list)
    for profile in profiles:
        buckets[profile.region].append(profile)
    clusters = list(buckets.values())
    clusters.sort(key=lambda group: sum(p.popularity for p in group), reverse=True)
    return clusters


def _cluster_distance(a: list[SpotProfile], b: list[SpotProfile]) -> float:
    total = 0.0
    count = 0
    for pa in a:
        for pb in b:
            total += haversine_km(pa.lat, pa.lng, pb.lat, pb.lng)
            count += 1
    return total / max(count, 1)


def _cluster_hours(cluster: list[SpotProfile]) -> float:
    return sum(p.duration_hours for p in cluster)


def _sort_clusters(
    clusters: list[list[SpotProfile]],
    *,
    sort_key: str,
    anchor_lat: float,
    anchor_lng: float,
) -> list[list[SpotProfile]]:
    if sort_key == "distance":
        clusters.sort(
            key=lambda group: haversine_km(anchor_lat, anchor_lng, group[0].lat, group[0].lng),
        )
    elif sort_key == "duration":
        clusters.sort(key=_cluster_hours, reverse=True)
    else:
        clusters.sort(key=lambda group: sum(p.popularity for p in group), reverse=True)
    return clusters


def _order_spots_greedy(
    spots: list[SpotProfile],
    *,
    anchor_lat: float,
    anchor_lng: float,
) -> list[SpotProfile]:
    if len(spots) <= 1:
        return spots
    remaining = spots.copy()
    ordered: list[SpotProfile] = []
    cur_lat, cur_lng = anchor_lat, anchor_lng
    while remaining:
        nxt = min(
            remaining,
            key=lambda p: haversine_km(cur_lat, cur_lng, p.lat, p.lng),
        )
        ordered.append(nxt)
        remaining.remove(nxt)
        cur_lat, cur_lng = nxt.lat, nxt.lng
    return ordered


def _flatten_ordered_profiles(
    profiles: list[SpotProfile],
    *,
    sort_key: str,
    anchor_lat: float,
    anchor_lng: float,
) -> list[SpotProfile]:
    clusters = _sort_clusters(_cluster_by_region(profiles), sort_key=sort_key, anchor_lat=anchor_lat, anchor_lng=anchor_lng)
    ordered: list[SpotProfile] = []
    for cluster in clusters:
        ordered.extend(_order_spots_greedy(cluster, anchor_lat=anchor_lat, anchor_lng=anchor_lng))
    return ordered


def _contiguous_slot_assignment(pool: list[str], slot_count: int) -> list[str]:
    if slot_count <= 0:
        return []
    if not pool:
        return [""] * slot_count
    base, extra = divmod(slot_count, len(pool))
    assigned: list[str] = []
    for index, spot in enumerate(pool):
        block = base + (1 if index < extra else 0)
        assigned.extend([spot] * block)
    return assigned[:slot_count]


def _filter_spots_for_weather(
    spots: list[SpotProfile],
    weather: DailyWeather | None,
) -> list[SpotProfile]:
    if not _is_rainy(weather):
        return spots
    indoor_first = sorted(
        spots,
        key=lambda p: (
            0 if (p.rain_ok or p.spot_type in {"indoor", "urban", "temple", "mixed"}) else 1,
            -p.popularity,
        ),
    )
    picked: list[SpotProfile] = []
    hours = 0.0
    for profile in indoor_first:
        if hours + profile.duration_hours > MAX_HOURS_PER_DAY:
            continue
        picked.append(profile)
        hours += profile.duration_hours
    return picked or indoor_first[:1]


def _assign_time_slots(
    spots: list[str],
    profiles: dict[str, SpotProfile],
) -> tuple[str | None, str | None, str | None]:
    if not spots:
        return None, None, None
    if len(spots) == 1:
        return None, None, None

    evening_candidates = [s for s in spots if profiles[s].sunset or profiles[s].best_time == "evening"]
    remaining = [s for s in spots if s not in evening_candidates]
    evening = evening_candidates[0] if evening_candidates else None

    if not remaining:
        return None, None, evening

    morning = next((s for s in remaining if profiles[s].best_time == "morning"), remaining[0])
    rest = [s for s in remaining if s != morning]
    afternoon = rest[0] if rest else None
    return morning, afternoon, evening


def _day_reason(
    spot_list: list[str],
    profiles: dict[str, SpotProfile],
    weather: DailyWeather | None,
    *,
    prefix: str = "",
) -> str:
    if not spot_list:
        return "当日无安排，可自由活动或休息调整。"
    filtered = [profiles[s] for s in spot_list if s in profiles]
    hours = sum(p.duration_hours for p in filtered)
    regions = sorted({p.region for p in filtered})
    parts: list[str] = []
    if prefix:
        parts.append(prefix)
    if len(regions) == 1:
        parts.append(f"同处{regions[0]}，减少跨区域交通")
    elif len(spot_list) > 1:
        parts.append("已按距离顺路串联")
    if _is_rainy(weather):
        parts.append("雨天优先安排室内/可雨天游览景点")
    elif any(p.sunset for p in filtered):
        parts.append("含日落观景点，建议傍晚留足时间")
    parts.append(f"预计游玩约 {hours:.1f} 小时")
    return "；".join(parts)


def _plan_equal_days(
    profiles: list[SpotProfile],
    dates: list[date],
    *,
    weather_by_date: dict[date, DailyWeather],
    profile_map: dict[str, SpotProfile],
) -> list[DayPlanDraft]:
    """One spot per day — no AM/PM/evening split."""
    remaining = list(profiles)
    day_plans: list[DayPlanDraft] = []

    for day in dates:
        if not remaining:
            day_plans.append(
                DayPlanDraft(
                    date=day,
                    spots=[],
                    reason="当日无安排，可自由活动或休息调整。",
                    use_time_slots=False,
                )
            )
            continue
        weather = weather_by_date.get(day)
        remaining.sort(key=lambda p: _weather_fit_score(p, weather), reverse=True)
        pick = remaining.pop(0)
        reason = _day_reason(
            [pick.name],
            profile_map,
            weather,
            prefix="每日一景，专注深度游览",
        )
        day_plans.append(
            DayPlanDraft(
                date=day,
                spots=[pick.name],
                reason=reason,
                use_time_slots=False,
            )
        )
    return day_plans


def _region_pack_score(day_spots: list[SpotProfile], candidate: SpotProfile) -> float:
    if not day_spots:
        return 0.0
    same_region = sum(1 for p in day_spots if p.region == candidate.region)
    dist = min(haversine_km(p.lat, p.lng, candidate.lat, candidate.lng) for p in day_spots)
    return same_region * 2.0 + max(0.0, 1.0 - dist / 30.0)


def _split_oversized_cluster(cluster: list[SpotProfile]) -> list[list[SpotProfile]]:
    if _cluster_hours(cluster) <= MAX_HOURS_PER_DAY:
        return [cluster]
    parts: list[list[SpotProfile]] = []
    current: list[SpotProfile] = []
    hours = 0.0
    for profile in sorted(cluster, key=lambda p: p.popularity, reverse=True):
        if current and hours + profile.duration_hours > MAX_HOURS_PER_DAY:
            parts.append(current)
            current = [profile]
            hours = profile.duration_hours
        else:
            current.append(profile)
            hours += profile.duration_hours
    if current:
        parts.append(current)
    return parts


def _ensure_non_empty_days(day_buckets: list[list[SpotProfile]]) -> None:
    n_days = len(day_buckets)
    for idx in range(n_days):
        if day_buckets[idx]:
            continue
        donor = max(
            (i for i in range(n_days) if len(day_buckets[i]) > 1),
            key=lambda i: len(day_buckets[i]),
            default=-1,
        )
        if donor < 0:
            donor = max(range(n_days), key=lambda i: len(day_buckets[i]))
        if day_buckets[donor]:
            day_buckets[idx].append(day_buckets[donor].pop())


def _plan_pack_days(
    profiles: list[SpotProfile],
    dates: list[date],
    *,
    weather_by_date: dict[date, DailyWeather],
    profile_map: dict[str, SpotProfile],
    sort_key: str,
    anchor_lat: float,
    anchor_lng: float,
) -> list[DayPlanDraft]:
    """More spots than days — fill every day; prefer whole region clusters on same day."""
    n_days = len(dates)
    n_spots = len(profiles)
    target_per_day = n_spots / n_days

    clusters = _sort_clusters(
        _cluster_by_region(profiles),
        sort_key=sort_key,
        anchor_lat=anchor_lat,
        anchor_lng=anchor_lng,
    )
    expanded: list[list[SpotProfile]] = []
    for cluster in clusters:
        expanded.extend(_split_oversized_cluster(cluster))

    day_buckets: list[list[SpotProfile]] = [[] for _ in range(n_days)]
    day_hours = [0.0 for _ in range(n_days)]
    spot_counts = [0 for _ in range(n_days)]

    for cluster in sorted(expanded, key=_cluster_hours, reverse=True):
        placed = False
        best_idx: int | None = None
        best_score = -1.0
        for idx in range(n_days):
            cluster_h = _cluster_hours(cluster)
            if day_hours[idx] + cluster_h > MAX_HOURS_PER_DAY:
                continue
            need = target_per_day - spot_counts[idx]
            score = need * 10.0 + _region_pack_score(day_buckets[idx], cluster[0])
            if score > best_score:
                best_score = score
                best_idx = idx
                placed = True
        if placed and best_idx is not None:
            day_buckets[best_idx].extend(cluster)
            day_hours[best_idx] += _cluster_hours(cluster)
            spot_counts[best_idx] += len(cluster)
            continue

        for profile in cluster:
            spot_best: int | None = None
            spot_score = -1.0
            for idx in range(n_days):
                if day_hours[idx] + profile.duration_hours > MAX_HOURS_PER_DAY:
                    continue
                need = target_per_day - spot_counts[idx]
                score = need * 10.0 + _region_pack_score(day_buckets[idx], profile)
                if score > spot_score:
                    spot_score = score
                    spot_best = idx
            if spot_best is None:
                spot_best = min(range(n_days), key=lambda i: day_hours[i])
            day_buckets[spot_best].append(profile)
            day_hours[spot_best] += profile.duration_hours
            spot_counts[spot_best] += 1

    _ensure_non_empty_days(day_buckets)

    day_plans: list[DayPlanDraft] = []
    for day, bucket in zip(dates, day_buckets, strict=False):
        weather = weather_by_date.get(day)
        ordered_day = _order_spots_greedy(bucket, anchor_lat=anchor_lat, anchor_lng=anchor_lng)
        filtered = _filter_spots_for_weather(ordered_day, weather)
        spot_names: list[str] = []
        hours = 0.0
        for profile in filtered:
            if hours + profile.duration_hours > MAX_HOURS_PER_DAY and spot_names:
                break
            spot_names.append(profile.name)
            hours += profile.duration_hours
        if not spot_names and bucket:
            spot_names = [bucket[0].name]

        day_plans.append(
            DayPlanDraft(
                date=day,
                spots=spot_names,
                reason=_day_reason(
                    spot_names,
                    profile_map,
                    weather,
                    prefix="多景点同日，顺路串联",
                ),
                use_time_slots=len(spot_names) > 1,
            )
        )
    return day_plans


def _plan_spread_days(
    profiles: list[SpotProfile],
    dates: list[date],
    *,
    weather_by_date: dict[date, DailyWeather],
    profile_map: dict[str, SpotProfile],
    sort_key: str,
    anchor_lat: float,
    anchor_lng: float,
) -> list[DayPlanDraft]:
    """Fewer spots than days — one spot may span multiple days via AM/PM blocks."""
    ordered = _flatten_ordered_profiles(
        profiles,
        sort_key=sort_key,
        anchor_lat=anchor_lat,
        anchor_lng=anchor_lng,
    )
    spot_names = [p.name for p in ordered]
    timeline: list[tuple[int, Literal["morning", "afternoon"]]] = []
    for day_idx in range(len(dates)):
        timeline.append((day_idx, "morning"))
        timeline.append((day_idx, "afternoon"))

    assignments = _contiguous_slot_assignment(spot_names, len(timeline))
    day_spot_names: list[list[str]] = [[] for _ in dates]
    day_morning: list[str | None] = [None for _ in dates]
    day_afternoon: list[str | None] = [None for _ in dates]

    for (day_idx, period), spot in zip(timeline, assignments, strict=False):
        if not spot:
            continue
        if spot not in day_spot_names[day_idx]:
            day_spot_names[day_idx].append(spot)
        if period == "morning":
            day_morning[day_idx] = spot
        else:
            day_afternoon[day_idx] = spot

    day_plans: list[DayPlanDraft] = []
    for idx, day in enumerate(dates):
        spots = day_spot_names[idx]
        weather = weather_by_date.get(day)
        morning = day_morning[idx]
        afternoon = day_afternoon[idx]
        use_slots = bool(
            spots
            and (
                len(spots) > 1
                or (morning and afternoon and morning != afternoon)
            )
        )
        reason_prefix = (
            "同一景点可跨天深度游览"
            if len(profiles) < len(dates)
            else "行程较宽松"
        )
        day_plans.append(
            DayPlanDraft(
                date=day,
                spots=spots,
                reason=_day_reason(spots, profile_map, weather, prefix=reason_prefix),
                use_time_slots=use_slots,
            )
        )
    return day_plans


def build_rule_clusters(
    spot_names: list[str],
    *,
    destination: str,
) -> list[list[SpotProfile]]:
    profiles = resolve_spot_profiles(spot_names, destination=destination)
    if not profiles:
        return []
    clusters = _cluster_by_region(profiles)
    expanded: list[list[SpotProfile]] = []
    for cluster in clusters:
        if _cluster_hours(cluster) <= MAX_HOURS_PER_DAY:
            expanded.append(cluster)
        else:
            parts: list[list[SpotProfile]] = []
            current: list[SpotProfile] = []
            hours = 0.0
            for profile in sorted(cluster, key=lambda p: p.popularity, reverse=True):
                if current and hours + profile.duration_hours > MAX_HOURS_PER_DAY:
                    parts.append(current)
                    current = [profile]
                    hours = profile.duration_hours
                else:
                    current.append(profile)
                    hours += profile.duration_hours
            if current:
                parts.append(current)
            expanded.extend(parts)
    return expanded


def plan_rule_route(
    spot_names: list[str],
    dates: list[date],
    *,
    destination: str,
    weather_by_date: dict[date, DailyWeather] | None = None,
    route_name: str = "Route A",
    sort_key: str = "popularity",
) -> RouteDraft:
    """Generate one route draft using geographic & weather rules."""
    weather_by_date = weather_by_date or {}
    anchor = get_city_anchor(destination)
    anchor_lat = anchor.lat if anchor else 0.0
    anchor_lng = anchor.lng if anchor else 0.0

    profiles = resolve_spot_profiles(spot_names, destination=destination)
    if not profiles or not dates:
        return RouteDraft(name=route_name, days=[])

    profile_map = _profile_map(profiles)
    mode = _planning_mode(len(profiles), len(dates))

    if mode == "equal":
        day_plans = _plan_equal_days(
            profiles,
            dates,
            weather_by_date=weather_by_date,
            profile_map=profile_map,
        )
    elif mode == "pack":
        day_plans = _plan_pack_days(
            profiles,
            dates,
            weather_by_date=weather_by_date,
            profile_map=profile_map,
            sort_key=sort_key,
            anchor_lat=anchor_lat,
            anchor_lng=anchor_lng,
        )
    else:
        day_plans = _plan_spread_days(
            profiles,
            dates,
            weather_by_date=weather_by_date,
            profile_map=profile_map,
            sort_key=sort_key,
            anchor_lat=anchor_lat,
            anchor_lng=anchor_lng,
        )

    return RouteDraft(name=route_name, days=day_plans)


def generate_rule_route_variants(
    spot_names: list[str],
    dates: list[date],
    *,
    destination: str,
    weather_by_date: dict[date, DailyWeather] | None = None,
) -> list[RouteDraft]:
    return [
        plan_rule_route(
            spot_names,
            dates,
            destination=destination,
            weather_by_date=weather_by_date,
            route_name="Route A",
            sort_key="popularity",
        ),
        plan_rule_route(
            spot_names,
            dates,
            destination=destination,
            weather_by_date=weather_by_date,
            route_name="Route B",
            sort_key="distance",
        ),
        plan_rule_route(
            spot_names,
            dates,
            destination=destination,
            weather_by_date=weather_by_date,
            route_name="Route C",
            sort_key="duration",
        ),
    ]


def route_draft_to_itinerary(
    route: RouteDraft,
    profiles: dict[str, SpotProfile],
) -> list[DayItinerary]:
    rows: list[DayItinerary] = []
    for day in route.days:
        if not day.spots:
            rows.append(
                DayItinerary(
                    date=day.date,
                    spot_names=[],
                    plan_reason=day.reason or None,
                )
            )
            continue
        if len(day.spots) == 1 or not day.use_time_slots:
            rows.append(
                DayItinerary(
                    date=day.date,
                    spot_names=list(day.spots),
                    morning=None,
                    afternoon=None,
                    evening=None,
                    plan_reason=day.reason or None,
                )
            )
            continue
        morning, afternoon, evening = _assign_time_slots(day.spots, profiles)
        rows.append(
            DayItinerary(
                date=day.date,
                spot_names=list(day.spots),
                morning=morning,
                afternoon=afternoon,
                evening=evening,
                plan_reason=day.reason or None,
            )
        )
    return rows


def rule_plan_to_itinerary(
    spot_names: list[str],
    dates: list[date],
    *,
    destination: str,
    weather_by_date: dict[date, DailyWeather] | None = None,
) -> list[DayItinerary]:
    from src.services.route_scorer import pick_best_route

    variants = generate_rule_route_variants(
        spot_names,
        dates,
        destination=destination,
        weather_by_date=weather_by_date,
    )
    profiles = _profile_map(resolve_spot_profiles(spot_names, destination=destination))
    best = pick_best_route(
        variants,
        profiles=profiles,
        weather_by_date=weather_by_date or {},
        preferences=None,
        anchor=get_city_anchor(destination),
    )
    return route_draft_to_itinerary(best.route, profiles)
