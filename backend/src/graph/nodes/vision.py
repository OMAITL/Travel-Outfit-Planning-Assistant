"""Vision Agent node — extract outfit elements from Xiaohongshu references."""

from __future__ import annotations

import json
from datetime import date

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.config import get_settings
from src.graph.state import (
    DayItinerary,
    DayOutfitTrend,
    NoteOutfitAnalysis,
    OutfitInspiration,
    PlanningState,
)
from src.services.itinerary import day_all_spots
from src.services.llm import (
    build_image_human_message,
    get_chat_model,
    get_vision_model,
    invoke_structured,
    load_prompt,
)
from src.services.trend_analysis import aggregate_day_trend
from src.tools.image_fetch import download_image_data_uri


class VisionBatchOutput(BaseModel):
    analyses: list[NoteOutfitAnalysis] = Field(default_factory=list)


def _analysis_shows_outfit(item: NoteOutfitAnalysis) -> bool:
    """True when vision found wearable items, even if the note title is a pose tutorial."""
    if item.is_outfit:
        return True
    garment_fields = (item.top, item.bottom, item.shoes, item.bag, item.accessories)
    return any(field.strip() for field in garment_fields)


def _inspirations_by_date(state: PlanningState) -> dict[date, list[OutfitInspiration]]:
    grouped: dict[date, list[OutfitInspiration]] = {}
    for ref in state.outfit_inspirations:
        grouped.setdefault(ref.trip_date, []).append(ref)
    return grouped


def _format_notes_for_day(refs: list[OutfitInspiration]) -> str:
    rows = []
    for ref in sorted(refs, key=lambda item: item.liked_count or 0, reverse=True):
        rows.append(
            json.dumps(
                {
                    "note_id": ref.note_id,
                    "title": ref.title,
                    "desc": ref.desc[:500] if ref.desc else "",
                    "liked_count": ref.liked_count,
                    "search_keyword": ref.search_keyword,
                },
                ensure_ascii=False,
            )
        )
    return "\n".join(rows)


def _collect_note_images(
    refs: list[OutfitInspiration],
    *,
    max_per_note: int,
) -> tuple[list[str], list[str]]:
    """Download note images as data URIs; return (data_uris, note_id order labels)."""
    data_uris: list[str] = []
    labels: list[str] = []
    for ref in sorted(refs, key=lambda item: item.liked_count or 0, reverse=True):
        urls: list[str] = []
        for candidate in [ref.cover_url, *ref.image_urls]:
            if candidate and candidate not in urls:
                urls.append(candidate)
            if len(urls) >= max_per_note:
                break
        downloaded = 0
        for url in urls:
            data_uri = download_image_data_uri(url)
            if data_uri:
                data_uris.append(data_uri)
                labels.append(ref.note_id)
                downloaded += 1
        if downloaded == 0:
            labels.append(ref.note_id)  # note has no fetchable image; analyzed by text only
    return data_uris, labels


def _merge_display_inspirations(
    inspirations: list[OutfitInspiration],
    *,
    outfit_note_ids: set[str],
    days: list[DayItinerary],
    target_per_day: int,
) -> list[OutfitInspiration]:
    """
    Build the XHS list shown in the report.

    Prefer vision-confirmed outfit notes, but backfill from the original day pool so
    a day never loses all references when the vision model is strict or fails partially.
    """
    if not inspirations:
        return inspirations

    by_date: dict[date, list[OutfitInspiration]] = {}
    for ref in inspirations:
        by_date.setdefault(ref.trip_date, []).append(ref)

    trip_dates = [row.date for row in days] if days else sorted(by_date.keys())
    merged: list[OutfitInspiration] = []

    for day in trip_dates:
        pool = sorted(
            by_date.get(day, []),
            key=lambda item: item.liked_count or 0,
            reverse=True,
        )
        day_refs: list[OutfitInspiration] = []
        seen_day: set[str] = set()

        for ref in pool:
            if ref.note_id not in outfit_note_ids:
                continue
            if ref.note_id in seen_day:
                continue
            seen_day.add(ref.note_id)
            day_refs.append(ref)
            if len(day_refs) >= target_per_day:
                break

        for ref in pool:
            if len(day_refs) >= target_per_day:
                break
            if ref.note_id in seen_day:
                continue
            seen_day.add(ref.note_id)
            day_refs.append(ref)

        if len(day_refs) >= target_per_day:
            merged.extend(day_refs[:target_per_day])

    return merged


def _finalize_inspirations_for_display(
    inspirations: list[OutfitInspiration],
    *,
    days: list[DayItinerary],
    target_per_day: int,
) -> list[OutfitInspiration]:
    """Dedupe by note_id per day and cap at target_per_day for the report UI."""
    return _merge_display_inspirations(
        inspirations,
        outfit_note_ids={ref.note_id for ref in inspirations},
        days=days,
        target_per_day=target_per_day,
    )


def _analyze_day(
    day: date,
    refs: list[OutfitInspiration],
    *,
    llm=None,
) -> list[NoteOutfitAnalysis]:
    if not refs:
        return []

    settings = get_settings()
    use_images = settings.vision_use_images and llm is None
    notes_block = _format_notes_for_day(refs)

    image_uris: list[str] = []
    image_labels: list[str] = []
    if use_images:
        image_uris, image_labels = _collect_note_images(
            refs,
            max_per_note=settings.vision_max_images_per_note,
        )

    if use_images and image_uris:
        model = get_vision_model()
        order_hint = "、".join(image_labels)
        user_text = (
            f"Trip date: {day}\n\n"
            "Below are Xiaohongshu outfit notes (text) followed by their photos.\n"
            "LOOK AT THE PHOTOS and describe the outfit ACTUALLY worn — do not guess from the title.\n"
            "Pose/拍照姿势 notes often show full outfits — extract clothing from those photos too.\n\n"
            f"Notes:\n{notes_block}\n\n"
            f"Images are attached in this note_id order: {order_hint}\n"
            "Set is_outfit=false only when photos show NO wearable outfit on a person "
            "(pure scenery, food, maps). Pose tutorials WITH visible clothing → is_outfit=true.\n"
            "Return one analysis object per note_id."
        )
        messages = [
            SystemMessage(content=load_prompt("vision.md")),
            build_image_human_message(user_text, image_uris),
        ]
    else:
        model = llm or get_chat_model()
        user_text = (
            f"Trip date: {day}\n\n"
            "Analyze these Xiaohongshu outfit notes (text only — no photos available):\n"
            f"{notes_block}\n\n"
            "Pose/拍照姿势 titles often still describe real outfits in the photos — infer garments when plausible.\n"
            "Set is_outfit=false only for pure scenery/food/maps with no clothing. "
            "Return one analysis object per note_id."
        )
        messages = [
            SystemMessage(content=load_prompt("vision.md")),
            HumanMessage(content=user_text),
        ]

    try:
        result: VisionBatchOutput = invoke_structured(
            model,
            VisionBatchOutput,
            messages,
            retries=1,
            operation="vision_analyze",
        )
        by_id = {item.note_id: item for item in result.analyses}
        ordered: list[NoteOutfitAnalysis] = []
        for ref in refs:
            if ref.note_id in by_id:
                ordered.append(by_id[ref.note_id])
        return ordered
    except Exception:
        return []


def vision_node(state: PlanningState, *, llm=None) -> PlanningState:
    if not state.outfit_inspirations:
        return state.append_trace(
            "Vision",
            "skipped: no XHS references to analyze",
            level="warning",
        )

    grouped = _inspirations_by_date(state)
    state = state.append_trace(
        "Vision",
        f"analyzing outfit elements for {len(grouped)} day(s)",
    )

    trends: list[DayOutfitTrend] = []
    outfit_note_ids: set[str] = set()
    dropped_total = 0
    for day, refs in sorted(grouped.items()):
        analyses = _analyze_day(day, refs, llm=llm)
        if not analyses:
            state = state.append_trace(
                "Vision",
                f"no structured analysis for {day}",
                level="warning",
            )
            continue

        # Keep notes where vision found garments — including pose tutorials with visible OOTD.
        outfit_analyses = [item for item in analyses if _analysis_shows_outfit(item)]
        dropped = len(analyses) - len(outfit_analyses)
        dropped_total += dropped
        if dropped:
            state = state.append_trace(
                "Vision",
                f"{day}: dropped {dropped} note(s) with no visible outfit in photos",
                level="warning",
            )
        if not outfit_analyses:
            state = state.append_trace(
                "Vision",
                f"{day}: no outfit-relevant notes after image review",
                level="warning",
            )
            continue
        outfit_note_ids.update(item.note_id for item in outfit_analyses)

        day_spots = []
        for row in state.itinerary:
            if row.date == day:
                day_spots = day_all_spots(row)
                break
        spot_name = "、".join(day_spots) if day_spots else (refs[0].search_keyword or "")
        trend = aggregate_day_trend(
            day,
            outfit_analyses,
            state.outfit_inspirations,
            destination=state.trip.destination if state.trip else "",
            spot_name=spot_name,
            gender=state.trip.preferences.gender if state.trip else None,
        )
        trends.append(trend)
        state = state.append_trace(
            "Vision",
            f"{day}: style={trend.dominant_style or '-'}, "
            f"tops={', '.join(trend.top_picks[:2]) or '-'}",
        )

    # Report UI: prefer vision-confirmed outfit notes, backfill so days stay populated.
    display_inspirations = _merge_display_inspirations(
        state.outfit_inspirations,
        outfit_note_ids=outfit_note_ids,
        days=state.itinerary,
        target_per_day=get_settings().justoneapi_xhs_notes_per_day,
    )
    update: dict = {"outfit_trends": trends}
    if display_inspirations:
        update["outfit_inspirations"] = display_inspirations
    state = state.append_trace(
        "Vision",
        f"display {len(display_inspirations)} XHS note(s), "
        f"vision-confirmed {len(outfit_note_ids)}, dropped {dropped_total}",
    )
    return state.model_copy(update=update)
