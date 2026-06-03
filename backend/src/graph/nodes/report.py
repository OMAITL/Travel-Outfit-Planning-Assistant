"""Report Agent node — assemble the final TravelReport."""

from __future__ import annotations

from datetime import date, timedelta

from src.graph.report import DailyReportCard, TravelReport
from src.graph.state import (
    DailyOutfit,
    DailyWeather,
    PlanningPhase,
    PlanningState,
    ProductCard,
)


def _weather_by_date(state: PlanningState) -> dict[date, DailyWeather]:
    return {day.date: day for day in state.weather}


def _outfit_by_date(state: PlanningState) -> dict[date, DailyOutfit]:
    return {outfit.date: outfit for outfit in state.outfits}


def _look_by_date(state: PlanningState) -> dict[date, str]:
    return {look.date: look.image_url for look in state.look_images}


def _products_by_date(state: PlanningState) -> dict[date, list[ProductCard]]:
    grouped: dict[date, list[ProductCard]] = {}
    for product in state.products:
        if product.trip_date is None:
            continue
        grouped.setdefault(product.trip_date, []).append(product)
    return grouped


def _iter_trip_dates(state: PlanningState) -> list[date]:
    if state.trip is None:
        return sorted(_outfit_by_date(state).keys())
    dates: list[date] = []
    current = state.trip.start_date
    while current <= state.trip.end_date:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def report_node(state: PlanningState) -> PlanningState:
    if state.trip is None:
        return state.append_trace("Report", "skipped: trip missing", level="warning")

    trip = state.trip
    weather_map = _weather_by_date(state)
    outfit_map = _outfit_by_date(state)
    look_map = _look_by_date(state)
    product_map = _products_by_date(state)

    daily_cards: list[DailyReportCard] = []
    for day in _iter_trip_dates(state):
        products = product_map.get(day, [])[:5]
        has_look = day in look_map
        degraded = (not has_look and day in outfit_map) or (not products and day in outfit_map)
        daily_cards.append(
            DailyReportCard(
                date=day,
                weather=weather_map.get(day),
                outfit=outfit_map.get(day),
                look_image_url=look_map.get(day),
                products=products,
                degraded=degraded,
            )
        )

    summary = (
        f"{trip.destination} {trip.trip_days} 日行程穿搭规划，"
        f"风格偏好：{trip.preferences.style}。"
    )

    report = TravelReport(
        destination=trip.destination,
        start_date=trip.start_date,
        end_date=trip.end_date,
        trip_days=trip.trip_days,
        daily_cards=daily_cards,
        summary=summary,
    )

    state = state.append_trace("Report", f"assembled report with {len(daily_cards)} day(s)")
    return state.model_copy(update={"report": report, "phase": PlanningPhase.DONE})
