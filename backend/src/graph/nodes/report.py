"""Report Agent node — assemble the final TravelReport."""

from __future__ import annotations

from datetime import date, timedelta

from app.utils.enrichment import parse_outfit_items
from app.utils.product_grouping import assign_products_to_items
from src.graph.report import DailyReportCard, OutfitItemView, ProductItemGroup, StyleReferenceView, TravelReport
from src.graph.state import (
    DailyOutfit,
    DailyWeather,
    OutfitInspiration,
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


def _inspirations_by_date(state: PlanningState) -> dict[date, list[OutfitInspiration]]:
    grouped: dict[date, list[OutfitInspiration]] = {}
    for ref in state.outfit_inspirations:
        grouped.setdefault(ref.trip_date, []).append(ref)
    return grouped


def _to_style_reference(ref: OutfitInspiration) -> StyleReferenceView:
    return StyleReferenceView(
        note_id=ref.note_id,
        title=ref.title,
        cover_url=ref.cover_url,
        image_urls=ref.image_urls,
        note_url=ref.note_url,
        user_name=ref.user_name,
        liked_count=ref.liked_count,
        search_keyword=ref.search_keyword,
    )


def _iter_trip_dates(state: PlanningState) -> list[date]:
    if state.trip is None:
        return sorted(_outfit_by_date(state).keys())
    dates: list[date] = []
    current = state.trip.start_date
    while current <= state.trip.end_date:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def _itinerary_by_date(state: PlanningState) -> dict[date, list[str]]:
    return {row.date: row.spot_names for row in state.itinerary}


def _build_product_groups(
    outfit: DailyOutfit | None,
    products: list[ProductCard],
) -> tuple[list[OutfitItemView], list[ProductItemGroup]]:
    if outfit is None:
        return [], []
    parsed = parse_outfit_items(outfit.outfit_summary)
    outfit_items = [OutfitItemView(label=label, text=text) for label, text in parsed]
    assigned = assign_products_to_items(outfit, products, max_per_item=3)
    groups: list[ProductItemGroup] = []
    for index, (label, text, group_products) in enumerate(assigned):
        cat_map = {"上装": "top", "内搭": "top", "外套": "top", "下装": "bottom", "鞋": "shoes", "配饰": "acc", "包": "acc"}
        category = cat_map.get(label, "top")
        short = text[:8] + ("…" if len(text) > 8 else "")
        groups.append(
            ProductItemGroup(
                id=f"{category}-{index}",
                label=f"{label}·{short}" if len(parsed) > 1 or label in {"上装", "外套"} else label,
                item_text=text,
                category=category,
                products=group_products[:3],
            )
        )
    return outfit_items, groups


def report_node(state: PlanningState) -> PlanningState:
    if state.trip is None:
        return state.append_trace("Report", "skipped: trip missing", level="warning")

    trip = state.trip
    weather_map = _weather_by_date(state)
    outfit_map = _outfit_by_date(state)
    look_map = _look_by_date(state)
    product_map = _products_by_date(state)
    inspiration_map = _inspirations_by_date(state)
    spot_map = _itinerary_by_date(state)

    daily_cards: list[DailyReportCard] = []
    for day in _iter_trip_dates(state):
        products = product_map.get(day, [])
        outfit = outfit_map.get(day)
        outfit_items, product_groups = _build_product_groups(outfit, products)
        has_look = day in look_map
        degraded = (not has_look and day in outfit_map) or (not products and day in outfit_map)
        daily_cards.append(
            DailyReportCard(
                date=day,
                spot_names=spot_map.get(day, []),
                weather=weather_map.get(day),
                outfit=outfit,
                outfit_items=outfit_items,
                product_groups=product_groups,
                look_image_url=look_map.get(day),
                style_references=[_to_style_reference(r) for r in inspiration_map.get(day, [])],
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
