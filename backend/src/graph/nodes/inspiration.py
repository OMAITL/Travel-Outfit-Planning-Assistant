"""Inspiration node — Xiaohongshu outfit references via Just One API."""

from __future__ import annotations

from src.config import get_settings
from src.graph.state import OutfitInspiration, PlanningState
from src.tools.justone_client import JustOneApiError
from src.tools.justone_xhs import fetch_outfit_inspirations


def _build_xhs_keyword(destination: str, style: str, spot_names: list[str]) -> str:
    spot = spot_names[0] if spot_names else destination
    style_part = style.split("、")[0].split(",")[0].strip() or "休闲"
    return f"{destination} {spot} 穿搭 {style_part}"


def inspiration_node(state: PlanningState) -> PlanningState:
    if not state.outfits:
        return state.append_trace("Inspiration", "skipped: no outfits", level="warning")

    if state.trip is None:
        return state.append_trace("Inspiration", "skipped: no trip", level="warning")

    settings = get_settings()
    if not settings.justoneapi_token:
        return state.append_trace("Inspiration", "skipped: JUSTONEAPI_TOKEN missing", level="warning")

    trip = state.trip
    prefs = trip.preferences
    max_notes = settings.justoneapi_xhs_notes_per_day
    max_calls = settings.justoneapi_xhs_max_calls_per_run
    fetch_detail = settings.justoneapi_xhs_fetch_detail

    inspirations: list[OutfitInspiration] = []
    calls_used = 0
    spot_map = {row.date: row.spot_names for row in state.itinerary}

    state = state.append_trace(
        "Inspiration",
        f"fetching XHS references for {len(state.outfits)} day(s), "
        f"max {max_notes} note(s)/day, {max_calls} API call(s)",
    )

    for outfit in state.outfits:
        if calls_used >= max_calls:
            break

        keyword = _build_xhs_keyword(
            trip.destination,
            prefs.style,
            spot_map.get(outfit.date, prefs.spot_names),
        )
        remaining = max_calls - calls_used
        try:
            notes, used = fetch_outfit_inspirations(
                keyword,
                max_notes=max_notes,
                fetch_detail=fetch_detail,
                max_api_calls=remaining,
            )
        except JustOneApiError as exc:
            state = (
                state.append_error(str(exc))
                .append_trace("Inspiration", f"XHS search failed: {keyword}", level="warning")
            )
            continue

        calls_used += used
        for note in notes:
            inspirations.append(
                OutfitInspiration(
                    trip_date=outfit.date,
                    note_id=note.note_id,
                    title=note.title,
                    cover_url=note.cover_url,
                    image_urls=note.image_urls[:6],
                    note_url=note.note_url,
                    user_name=note.user_name,
                    liked_count=note.liked_count,
                    search_keyword=keyword,
                )
            )

        if not notes:
            state = state.append_trace(
                "Inspiration",
                f"no XHS notes for {outfit.date} ({keyword})",
                level="warning",
            )

    state = state.append_trace(
        "Inspiration",
        f"collected {len(inspirations)} reference note(s), {calls_used} API call(s)",
    )
    return state.model_copy(update={"outfit_inspirations": inspirations})
