"""Image Agent node — generate AI outfit look images with scenic backgrounds."""

from __future__ import annotations

from src.config import get_settings
from src.graph.state import OutfitInspiration, OutfitLookImage, PlanningState
from src.tools.image_gen import build_outfit_prompt, generate_outfit_look
from src.tools.scenic_scene import unique_spots_for_images


def _weather_summary_for_date(state: PlanningState, outfit_date) -> str:
    for day in state.weather:
        if day.date == outfit_date:
            condition = day.condition.value if hasattr(day.condition, "value") else day.condition
            return f"{condition}, {day.temp_min:.0f}~{day.temp_max:.0f}°C"
    return "weather unavailable"


def _spots_for_date(state: PlanningState, outfit_date) -> list[str]:
    for row in state.itinerary:
        if row.date == outfit_date:
            return row.spot_names
    return []


def _inspirations_for_date(state: PlanningState, outfit_date) -> list[OutfitInspiration]:
    return [ref for ref in state.outfit_inspirations if ref.trip_date == outfit_date]


def _trend_for_date(state: PlanningState, outfit_date):
    for trend in state.outfit_trends:
        if trend.date == outfit_date:
            return trend
    return None


def _reference_url_priority(url: str) -> int:
    """Lower is better for Jimeng i2i (JPG preview beats HEIF original)."""
    lower = url.lower()
    if "format/jpg" in lower or "format/jpeg" in lower:
        return 0
    if "format/webp" in lower:
        return 1
    if "format/heif" in lower:
        return 3
    return 2


def _pick_reference_image(inspirations: list[OutfitInspiration]) -> tuple[str | None, str]:
    """Return (best image URL, style hint from note titles) for i2i generation."""
    if not inspirations:
        return None, ""

    ranked = sorted(
        inspirations,
        key=lambda ref: ref.liked_count or 0,
        reverse=True,
    )
    hints = [ref.title for ref in ranked if ref.title][:2]
    hint = "；".join(hints)

    candidates: list[str] = []
    for ref in ranked:
        for url in [ref.cover_url, *ref.image_urls]:
            if url and url not in candidates:
                candidates.append(url)
    if not candidates:
        return None, hint

    candidates.sort(key=_reference_url_priority)
    return candidates[0], hint


def image_node(state: PlanningState) -> PlanningState:
    if not state.outfits:
        return state.append_trace("Image", "skipped: no outfits", level="warning")

    if state.trip is None:
        return state.append_trace("Image", "skipped: trip missing", level="warning")

    if get_settings().skip_image_generation:
        return state.append_trace(
            "Image",
            "skipped: SKIP_IMAGE_GENERATION enabled",
            level="warning",
        ).model_copy(update={"look_images": []})

    trip = state.trip
    prefs = trip.preferences
    look_images: list[OutfitLookImage] = []
    state = state.append_trace(
        "Image",
        f"generating look images for {len(state.outfits)} day(s) "
        "via text-to-image from planned outfit items",
    )

    for outfit in state.outfits:
        day_spots = _spots_for_date(state, outfit.date)
        spots_to_render = unique_spots_for_images(day_spots, trip.destination)

        for spot_name in spots_to_render:
            prompt = build_outfit_prompt(
                destination=trip.destination,
                date=str(outfit.date),
                weather_summary=_weather_summary_for_date(state, outfit.date),
                outfit_summary=outfit.outfit_summary,
                style=prefs.style,
                gender=prefs.gender,
                activities=prefs.activities,
                spot_name=spot_name,
            )

            image_url = generate_outfit_look(prompt, reference_image_url=None)
            if image_url:
                look_images.append(
                    OutfitLookImage(
                        date=outfit.date,
                        spot_name=spot_name,
                        image_url=image_url,
                        prompt=prompt,
                    )
                )
                state = state.append_trace(
                    "Image",
                    f"generated look for {outfit.date} @ {spot_name}",
                )
            else:
                state = (
                    state.append_error(
                        f"Image generation failed for {outfit.date} @ {spot_name}"
                    )
                    .append_trace(
                        "Image",
                        f"failed for {outfit.date} @ {spot_name}",
                        level="warning",
                    )
                )

    return state.model_copy(update={"look_images": look_images})
