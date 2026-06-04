"""Image Agent node — generate AI outfit look images with scenic backgrounds."""

from __future__ import annotations

from src.graph.state import OutfitLookImage, PlanningState
from src.tools.image_gen import build_outfit_prompt, generate_outfit_look
from src.tools.scenic_scene import primary_spot_for_day


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


def image_node(state: PlanningState) -> PlanningState:
    if not state.outfits:
        return state.append_trace("Image", "skipped: no outfits", level="warning")

    if state.trip is None:
        return state.append_trace("Image", "skipped: trip missing", level="warning")

    from src.config import get_settings

    if get_settings().skip_image_generation:
        return state.append_trace(
            "Image",
            "skipped: SKIP_IMAGE_GENERATION enabled",
            level="warning",
        ).model_copy(update={"look_images": []})

    trip = state.trip
    prefs = trip.preferences
    look_images: list[OutfitLookImage] = []
    state = state.append_trace("Image", f"generating look images for {len(state.outfits)} day(s)")

    for outfit in state.outfits:
        day_spots = _spots_for_date(state, outfit.date)
        spot_name = primary_spot_for_day(day_spots, trip.destination)
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
        image_url = generate_outfit_look(prompt)
        if image_url:
            look_images.append(
                OutfitLookImage(date=outfit.date, image_url=image_url, prompt=prompt)
            )
            state = state.append_trace(
                "Image",
                f"generated look for {outfit.date} @ {spot_name}",
            )
        else:
            state = (
                state.append_error(f"Image generation failed for {outfit.date}")
                .append_trace("Image", f"failed for {outfit.date}", level="warning")
            )

    return state.model_copy(update={"look_images": look_images})
