"""Aggregate Xiaohongshu note analyses into daily outfit trends."""

from __future__ import annotations

from collections import Counter
from datetime import date

from src.graph.state import DayOutfitTrend, NoteOutfitAnalysis, OutfitInspiration, XhsStyleProfile


def _top_values(analyses: list[NoteOutfitAnalysis], field: str, limit: int = 3) -> list[str]:
    counter: Counter[str] = Counter()
    for analysis in analyses:
        value = getattr(analysis, field, "").strip()
        if value:
            counter[value] += 1
    return [item for item, _ in counter.most_common(limit)]


def _dominant_style(analyses: list[NoteOutfitAnalysis]) -> str:
    styles = _top_values(analyses, "style", limit=1)
    return styles[0] if styles else ""


def _dominant_palette(analyses: list[NoteOutfitAnalysis]) -> str:
    palettes = _top_values(analyses, "color_palette", limit=1)
    return palettes[0] if palettes else ""


def _dominant_scene(analyses: list[NoteOutfitAnalysis]) -> str:
    scenes = _top_values(analyses, "scene_vibe", limit=1)
    return scenes[0] if scenes else ""


def _dominant_photo_style(analyses: list[NoteOutfitAnalysis]) -> str:
    styles = _top_values(analyses, "photo_style", limit=1)
    return styles[0] if styles else ""


def _best_editorial_prompt(
    analyses: list[NoteOutfitAnalysis],
    inspirations: list[OutfitInspiration],
) -> str:
    liked_by_note = {ref.note_id: ref.liked_count or 0 for ref in inspirations}
    ranked = sorted(
        analyses,
        key=lambda item: liked_by_note.get(item.note_id, 0),
        reverse=True,
    )
    for analysis in ranked:
        if analysis.image_prompt_en.strip():
            return analysis.image_prompt_en.strip()
    return ""


def build_editorial_prompt(
    *,
    destination: str,
    spot_name: str,
    trend: DayOutfitTrend,
    gender: str | None = None,
) -> str:
    """Synthesize an English editorial prompt when vision did not provide one."""
    gender_text = gender or "young Asian woman"
    top = trend.top_picks[0] if trend.top_picks else "stylish top"
    bottom = trend.bottom_picks[0] if trend.bottom_picks else "coordinated bottoms"
    shoes = trend.shoes_picks[0] if trend.shoes_picks else "trendy sneakers"
    style = trend.dominant_style or "clean girl"
    colors = trend.color_palette or "neutral tones"
    photo = trend.photo_style or "instagram fashion photography, natural light"
    scene = trend.scene_vibe or f"{spot_name} street in {destination}"
    return (
        f"A {gender_text} in {scene}, wearing {top}, {bottom}, {shoes}, "
        f"{style} style, color palette {colors}, full body mid-distance, "
        f"{photo}, high-end editorial travel outfit photo, no text or watermark."
    )


def build_style_profile(analyses: list[NoteOutfitAnalysis]) -> XhsStyleProfile:
    """Extract common outfit patterns from high-liked note analyses."""
    colors: list[str] = []
    for analysis in analyses:
        palette = analysis.color_palette.strip()
        if palette:
            for part in palette.replace("、", ",").replace("/", ",").split(","):
                cleaned = part.strip()
                if cleaned:
                    colors.append(cleaned)

    color_counter: Counter[str] = Counter(colors)
    recommended_colors = [item for item, _ in color_counter.most_common(5)]

    return XhsStyleProfile(
        top_style=_dominant_style(analyses),
        common_tops=_top_values(analyses, "top", limit=5),
        common_bottoms=_top_values(analyses, "bottom", limit=5),
        common_shoes=_top_values(analyses, "shoes", limit=3),
        common_accessories=_top_values(analyses, "accessories", limit=3),
        recommended_colors=recommended_colors,
    )


def aggregate_day_trend(
    day: date,
    analyses: list[NoteOutfitAnalysis],
    inspirations: list[OutfitInspiration],
    *,
    destination: str = "",
    spot_name: str = "",
    gender: str | None = None,
) -> DayOutfitTrend:
    """Merge per-note vision output into ranked picks for stylist/shopping/image."""
    day_refs = [ref for ref in inspirations if ref.trip_date == day]
    editorial = _best_editorial_prompt(analyses, day_refs)
    style_profile = build_style_profile(analyses)
    trend = DayOutfitTrend(
        date=day,
        dominant_style=style_profile.top_style or _dominant_style(analyses),
        top_picks=style_profile.common_tops or _top_values(analyses, "top"),
        bottom_picks=style_profile.common_bottoms or _top_values(analyses, "bottom"),
        shoes_picks=style_profile.common_shoes or _top_values(analyses, "shoes"),
        bag_picks=_top_values(analyses, "bag"),
        acc_picks=style_profile.common_accessories or _top_values(analyses, "accessories"),
        color_palette=", ".join(style_profile.recommended_colors) or _dominant_palette(analyses),
        scene_vibe=_dominant_scene(analyses),
        photo_style=_dominant_photo_style(analyses),
        editorial_prompt_en=editorial,
        style_profile=style_profile,
        note_analyses=analyses,
    )
    if not trend.editorial_prompt_en and analyses:
        dest = destination or "travel destination"
        spot = spot_name or dest
        trend = trend.model_copy(
            update={
                "editorial_prompt_en": build_editorial_prompt(
                    destination=dest,
                    spot_name=spot,
                    trend=trend,
                    gender=gender,
                )
            }
        )
    return trend
