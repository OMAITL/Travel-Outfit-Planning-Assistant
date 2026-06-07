"""Report Agent node — assemble the final TravelReport."""

from __future__ import annotations

from datetime import date, timedelta

from app.utils.enrichment import expand_outfit_item_slots, is_purchasable_item_text, parse_outfit_items
from app.utils.product_grouping import assign_products_to_items
from src.graph.report import DailyReportCard, OutfitItemView, ProductItemGroup, StyleReferenceView, TravelReport
from src.graph.state import (
    DailyOutfit,
    DailyWeather,
    DayItinerary,
    OutfitInspiration,
    PlanningPhase,
    PlanningState,
    ProductCard,
)


def _weather_by_date(state: PlanningState) -> dict[date, DailyWeather]:
    return {day.date: day for day in state.weather}


def _outfit_by_date(state: PlanningState) -> dict[date, DailyOutfit]:
    return {outfit.date: outfit for outfit in state.outfits}


def _looks_by_date(state: PlanningState) -> dict[date, dict[str, str]]:
    grouped: dict[date, dict[str, str]] = {}
    for look in state.look_images:
        spot_key = look.spot_name or ""
        grouped.setdefault(look.date, {})[spot_key] = look.image_url
    return grouped


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


def _unique_style_references(refs: list[OutfitInspiration], *, limit: int = 3) -> list[StyleReferenceView]:
    seen: set[str] = set()
    unique: list[StyleReferenceView] = []
    for ref in sorted(refs, key=lambda r: r.liked_count or 0, reverse=True):
        if ref.note_id in seen:
            continue
        seen.add(ref.note_id)
        unique.append(_to_style_reference(ref))
        if len(unique) >= limit:
            break
    return unique


def _iter_trip_dates(state: PlanningState) -> list[date]:
    if state.trip is None:
        return sorted(_outfit_by_date(state).keys())
    dates: list[date] = []
    current = state.trip.start_date
    while current <= state.trip.end_date:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def _itinerary_by_date(state: PlanningState) -> dict[date, DayItinerary]:
    return {row.date: row for row in state.itinerary}


def _build_product_groups(
    outfit: DailyOutfit | None,
    products: list[ProductCard],
) -> tuple[list[OutfitItemView], list[ProductItemGroup]]:
    if outfit is None:
        return [], []
    parsed = [
        (label, text)
        for label, text in expand_outfit_item_slots(parse_outfit_items(outfit.outfit_summary))
        if is_purchasable_item_text(text)
    ]
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


def _flatten_group_products(
    groups: list[ProductItemGroup],
    *,
    limit: int = 12,
) -> list[ProductCard]:
    """Dedupe products from groups for the flat card list (schema max 12)."""
    seen: set[str] = set()
    flat: list[ProductCard] = []
    for group in groups:
        for product in group.products:
            key = product.num_iid or product.detail_url or product.title
            if key in seen:
                continue
            seen.add(key)
            flat.append(product)
            if len(flat) >= limit:
                return flat
    return flat


def report_node(state: PlanningState) -> PlanningState:
    if state.trip is None:
        return state.append_trace("Report", "skipped: trip missing", level="warning")

    trip = state.trip
    weather_map = _weather_by_date(state)
    outfit_map = _outfit_by_date(state)
    look_map = _looks_by_date(state)
    product_map = _products_by_date(state)
    inspiration_map = _inspirations_by_date(state)
    itinerary_map = _itinerary_by_date(state)

    daily_cards: list[DailyReportCard] = []
    for day in _iter_trip_dates(state):
        products = product_map.get(day, [])
        outfit = outfit_map.get(day)
        outfit_items, product_groups = _build_product_groups(outfit, products)
        card_products = _flatten_group_products(product_groups)
        day_looks = look_map.get(day, {})
        spot_names = day_plan.spot_names if (day_plan := itinerary_map.get(day)) else []
        primary_look = next(
            (day_looks[name] for name in spot_names if name in day_looks),
            day_looks.get("") or next(iter(day_looks.values()), None),
        )
        has_look = bool(day_looks)
        degraded = (not has_look and day in outfit_map) or (not card_products and day in outfit_map)
        daily_cards.append(
            DailyReportCard(
                date=day,
                spot_names=spot_names,
                morning=day_plan.morning if day_plan else None,
                afternoon=day_plan.afternoon if day_plan else None,
                evening=day_plan.evening if day_plan else None,
                weather=weather_map.get(day),
                outfit=outfit,
                outfit_items=outfit_items,
                product_groups=product_groups,
                look_image_url=primary_look,
                look_images_by_spot={
                    name: url for name, url in day_looks.items() if name
                },
                style_references=_unique_style_references(inspiration_map.get(day, [])),
                products=card_products,
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
