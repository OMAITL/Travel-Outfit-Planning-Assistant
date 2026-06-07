"""Inspiration node — XHS search via Outfit Query Compiler."""

from __future__ import annotations

import logging
from collections import defaultdict

from src.config import get_settings
from src.graph.state import DayItinerary, OutfitInspiration, PlanningState, XhsQueryDebugEntry
from src.services.itinerary import day_all_spots, iter_trip_dates
from src.services.outfit_query_compiler import (
    OutfitQueryCompiler,
    OutfitSearchProfile,
    XhsFilterStats,
    note_rejected_by_profile,
    profile_from_preferences,
)
from src.tools.justone_client import JustOneApiError
from src.tools.justone_xhs import XhsNoteSummary, get_xhs_note_detail, search_xhs_notes

logger = logging.getLogger(__name__)


def _planning_days(state: PlanningState) -> list[DayItinerary]:
    if state.itinerary:
        return state.itinerary
    if state.trip is None:
        return []
    prefs = state.trip.preferences
    return [
        DayItinerary(date=day, spot_names=prefs.spot_names)
        for day in iter_trip_dates(state.trip.start_date, state.trip.end_date)
    ]


def _merge_note(existing: XhsNoteSummary | None, incoming: XhsNoteSummary) -> XhsNoteSummary:
    if existing is None:
        return incoming
    if (incoming.liked_count or 0) > (existing.liked_count or 0):
        return incoming
    return existing


_NON_OUTFIT_HINTS = (
    "攻略",
    "路线",
    "行程",
    "避雷",
    "美食",
    "探店",
    "门票",
    "住宿",
    "民宿",
    "酒店",
    "交通",
    "自驾",
)
_OUTFIT_HINTS = ("穿搭", "ootd", "outfit", "搭配", "衣服", "裙", "裤", "上衣", "外套", "鞋", "look", "造型")


def _looks_non_outfit(note: XhsNoteSummary) -> bool:
    text = f"{note.title} {note.desc}".lower()
    if any(cue in text for cue in _OUTFIT_HINTS):
        return False
    return any(bad in text for bad in _NON_OUTFIT_HINTS)


def _is_xhs_quota_error(exc: JustOneApiError) -> bool:
    return exc.error_code in {"303", "601"}


def _merge_search_note(existing: XhsNoteSummary, incoming: XhsNoteSummary) -> XhsNoteSummary:
    merged_urls = list(incoming.image_urls)
    for url in existing.image_urls:
        if url not in merged_urls:
            merged_urls.append(url)
    return XhsNoteSummary(
        note_id=incoming.note_id,
        title=incoming.title or existing.title,
        cover_url=incoming.cover_url or existing.cover_url,
        image_urls=merged_urls or existing.image_urls,
        note_url=incoming.note_url or existing.note_url,
        desc=incoming.desc or existing.desc,
        liked_count=incoming.liked_count or existing.liked_count,
        user_name=incoming.user_name or existing.user_name,
        note_type=incoming.note_type or existing.note_type,
    )


def _note_passes_filters(
    note: XhsNoteSummary,
    profile: OutfitSearchProfile,
    *,
    min_liked: int,
    stats: XhsFilterStats,
) -> bool:
    if min_liked and (note.liked_count or 0) < min_liked:
        stats.low_likes += 1
        return False
    if _looks_non_outfit(note):
        stats.non_outfit += 1
        return False
    if note_rejected_by_profile(note, profile):
        stats.avoid += 1
        return False
    return bool(note.cover_url or note.image_urls)


def _collect_day_notes(
    query_plan: list[tuple[str, OutfitSearchProfile]],
    *,
    max_notes: int,
    fetch_detail: bool,
    max_api_calls: int,
    min_liked: int,
    exclude_note_ids: set[str] | None = None,
    stats_by_spot: dict[str, XhsFilterStats] | None = None,
) -> tuple[list[tuple[XhsNoteSummary, str]], int]:
    """Search and filter until max_notes pass or API budget is exhausted."""
    merged: dict[str, tuple[XhsNoteSummary, str]] = {}
    calls = 0
    excluded = exclude_note_ids or set()
    stats = stats_by_spot if stats_by_spot is not None else defaultdict(XhsFilterStats)

    for keyword, profile in query_plan:
        if len(merged) >= max_notes or calls >= max_api_calls:
            break
        spot_key = profile.spot
        try:
            candidates = search_xhs_notes(keyword, include_ads=False)
        except JustOneApiError:
            raise
        calls += 1

        for candidate in candidates:
            if len(merged) >= max_notes or calls >= max_api_calls:
                break
            if candidate.note_id in excluded or candidate.note_id in merged:
                continue
            if not _note_passes_filters(candidate, profile, min_liked=min_liked, stats=stats[spot_key]):
                continue

            note = candidate
            if fetch_detail and calls < max_api_calls:
                try:
                    detailed = get_xhs_note_detail(candidate.note_id)
                    calls += 1
                    if detailed is not None:
                        note = _merge_search_note(candidate, detailed)
                except JustOneApiError:
                    note = candidate

            if not _note_passes_filters(note, profile, min_liked=min_liked, stats=stats[spot_key]):
                continue
            merged[note.note_id] = (note, keyword)

    ranked = sorted(
        merged.values(),
        key=lambda pair: pair[0].liked_count or 0,
        reverse=True,
    )
    return ranked[:max_notes], calls


def _debug_entry_from_compile(
    trip_date,
    compiled,
    stats: XhsFilterStats,
    notes_kept: int,
) -> XhsQueryDebugEntry:
    return XhsQueryDebugEntry(
        trip_date=trip_date,
        spot=compiled.profile.spot,
        profile=compiled.profile.model_dump(mode="json"),
        final_query=compiled.final_query,
        base_tokens=[item.model_dump() for item in compiled.base_tokens],
        expanded_queries=list(compiled.expanded_queries),
        compile_source=compiled.source,
        filtered_avoid=stats.avoid,
        filtered_non_outfit=stats.non_outfit,
        filtered_low_likes=stats.low_likes,
        notes_kept=notes_kept,
    )


def inspiration_node(state: PlanningState) -> PlanningState:
    if state.trip is None or not state.trip.is_complete:
        return state.append_trace("Inspiration", "skipped: trip not ready", level="warning")

    settings = get_settings()
    if not settings.justoneapi_token:
        return state.append_trace(
            "Inspiration",
            "skipped: JUSTONEAPI_TOKEN missing",
            level="warning",
        )

    trip = state.trip
    prefs = trip.preferences
    days = _planning_days(state)
    if not days:
        return state.append_trace("Inspiration", "skipped: no trip days", level="warning")

    max_notes = settings.justoneapi_xhs_notes_per_day
    max_calls = settings.justoneapi_xhs_max_calls_per_run
    fetch_detail = settings.justoneapi_xhs_fetch_detail
    min_liked = settings.justoneapi_xhs_min_liked

    compiler = OutfitQueryCompiler()
    inspirations: list[OutfitInspiration] = []
    query_debug: list[XhsQueryDebugEntry] = []
    calls_used = 0
    xhs_quota_exceeded = False

    state = state.append_trace(
        "Inspiration",
        f"XHS Query Compiler: {len(days)} day(s), "
        f"target {max_notes} note(s)/day, llm_expand={settings.xhs_query_llm_expand}",
    )

    for row in days:
        if calls_used >= max_calls:
            break

        day_spots = day_all_spots(row) or prefs.spot_names or [trip.destination]
        query_rows = compiler.compile_queries_for_spots(
            prefs,
            destination=trip.destination,
            spots=day_spots,
            trip_date=row.date,
        )
        if not query_rows:
            profile = profile_from_preferences(
                prefs,
                destination=trip.destination,
                spot=trip.destination,
                trip_date=row.date,
            )
            compiled = compiler.compile(profile)
            query_rows = [(compiled.final_query, compiled)]

        query_plan = [(keyword, compiled.profile) for keyword, compiled in query_rows]
        stats_by_spot: dict[str, XhsFilterStats] = defaultdict(XhsFilterStats)
        compiled_by_spot = {compiled.profile.spot: compiled for _, compiled in query_rows}

        detail_budget = 1 if fetch_detail else 0
        calls_per_day = max(
            len(query_plan) + max_notes * (1 + detail_budget),
            max_calls // max(len(days), 1),
        )
        remaining = min(calls_per_day, max_calls - calls_used)
        if remaining <= 0:
            break
        day_assigned_ids = {r.note_id for r in inspirations if r.trip_date == row.date}
        try:
            notes, used = _collect_day_notes(
                query_plan,
                max_notes=max_notes,
                fetch_detail=fetch_detail,
                max_api_calls=remaining,
                min_liked=min_liked,
                exclude_note_ids=day_assigned_ids,
                stats_by_spot=stats_by_spot,
            )
        except JustOneApiError as exc:
            if _is_xhs_quota_error(exc):
                xhs_quota_exceeded = True
                logger.warning("XHS API quota exceeded for %s: %s", row.date, exc)
            state = (
                state.append_error(str(exc))
                .append_trace(
                    "Inspiration",
                    f"XHS search failed for {row.date}: {exc}",
                    level="warning",
                )
            )
            continue

        calls_used += used
        notes_by_spot: dict[str, int] = defaultdict(int)
        for note, search_keyword in notes:
            if note.note_id in day_assigned_ids:
                continue
            day_assigned_ids.add(note.note_id)
            matched_spot = next(
                (compiled.profile.spot for kw, compiled in query_rows if kw == search_keyword),
                day_spots[0],
            )
            notes_by_spot[matched_spot] += 1
            inspirations.append(
                OutfitInspiration(
                    trip_date=row.date,
                    note_id=note.note_id,
                    title=note.title,
                    desc=note.desc,
                    cover_url=note.cover_url,
                    image_urls=note.image_urls[:6],
                    note_url=note.note_url,
                    user_name=note.user_name,
                    liked_count=note.liked_count,
                    search_keyword=search_keyword,
                )
            )

        for spot in day_spots:
            compiled = compiled_by_spot.get(spot) or compiler.compile(
                profile_from_preferences(
                    prefs,
                    destination=trip.destination,
                    spot=spot,
                    trip_date=row.date,
                )
            )
            entry = _debug_entry_from_compile(
                row.date,
                compiled,
                stats_by_spot.get(spot, XhsFilterStats()),
                notes_by_spot.get(spot, 0),
            )
            query_debug.append(entry)
            token_summary = " · ".join(f"{t['rule']}:{t['token']}" for t in entry.base_tokens)
            state = state.append_trace(
                "QueryCompiler",
                f"{row.date} @{spot} →「{entry.final_query}」"
                f" | 规则[{token_summary}]"
                f" | 过滤(雷点{entry.filtered_avoid}/非穿搭{entry.filtered_non_outfit})"
                f" | 保留{entry.notes_kept}条",
            )

        if len(notes) < max_notes and calls_used < max_calls:
            for spot in day_spots:
                if len([r for r in inspirations if r.trip_date == row.date]) >= max_notes:
                    break
                if calls_used >= max_calls:
                    break
                profile = profile_from_preferences(
                    prefs,
                    destination=trip.destination,
                    spot=spot,
                    trip_date=row.date,
                )
                compiled = compiler.compile(profile)
                extra_plan = [(compiled.final_query, profile)]
                extra_remaining = min(2, max_calls - calls_used)
                extra_stats: dict[str, XhsFilterStats] = defaultdict(XhsFilterStats)
                try:
                    extra_notes, extra_used = _collect_day_notes(
                        extra_plan,
                        max_notes=max_notes,
                        fetch_detail=fetch_detail,
                        max_api_calls=extra_remaining,
                        min_liked=min_liked,
                        exclude_note_ids=day_assigned_ids,
                        stats_by_spot=extra_stats,
                    )
                except JustOneApiError:
                    break
                calls_used += extra_used
                for note, search_keyword in extra_notes:
                    if note.note_id in day_assigned_ids:
                        continue
                    day_count = len([r for r in inspirations if r.trip_date == row.date])
                    if day_count >= max_notes:
                        break
                    day_assigned_ids.add(note.note_id)
                    inspirations.append(
                        OutfitInspiration(
                            trip_date=row.date,
                            note_id=note.note_id,
                            title=note.title,
                            desc=note.desc,
                            cover_url=note.cover_url,
                            image_urls=note.image_urls[:6],
                            note_url=note.note_url,
                            user_name=note.user_name,
                            liked_count=note.liked_count,
                            search_keyword=search_keyword,
                        )
                    )

        day_count = len([r for r in inspirations if r.trip_date == row.date])
        if day_count < max_notes and min_liked > 0 and calls_used < max_calls:
            relaxed_remaining = min(max_calls - calls_used, max_notes * 2)
            relaxed_stats: dict[str, XhsFilterStats] = defaultdict(XhsFilterStats)
            try:
                relaxed_notes, relaxed_used = _collect_day_notes(
                    query_plan,
                    max_notes=max_notes - day_count,
                    fetch_detail=fetch_detail,
                    max_api_calls=relaxed_remaining,
                    min_liked=0,
                    exclude_note_ids=day_assigned_ids,
                    stats_by_spot=relaxed_stats,
                )
            except JustOneApiError:
                relaxed_notes, relaxed_used = [], 0
            calls_used += relaxed_used
            for note, search_keyword in relaxed_notes:
                if note.note_id in day_assigned_ids:
                    continue
                if len([r for r in inspirations if r.trip_date == row.date]) >= max_notes:
                    break
                day_assigned_ids.add(note.note_id)
                inspirations.append(
                    OutfitInspiration(
                        trip_date=row.date,
                        note_id=note.note_id,
                        title=note.title,
                        desc=note.desc,
                        cover_url=note.cover_url,
                        image_urls=note.image_urls[:6],
                        note_url=note.note_url,
                        user_name=note.user_name,
                        liked_count=note.liked_count,
                        search_keyword=search_keyword,
                    )
                )
            if relaxed_notes:
                state = state.append_trace(
                    "Inspiration",
                    f"{row.date}: relaxed min_liked to 0, added {len(relaxed_notes)} note(s)",
                )
            day_count = len([r for r in inspirations if r.trip_date == row.date])

        if day_count < max_notes:
            logger.warning(
                "XHS notes incomplete for %s: got %d/%d (calls_used=%d/%d, quota=%s)",
                row.date,
                day_count,
                max_notes,
                calls_used,
                max_calls,
                xhs_quota_exceeded,
            )
            inspirations = [r for r in inspirations if r.trip_date != row.date]
            state = state.append_trace(
                "Inspiration",
                f"{row.date}: only {day_count}/{max_notes} XHS notes — cleared for UI "
                f"(quota={'yes' if xhs_quota_exceeded or calls_used >= max_calls else 'filter/budget'})",
                level="warning",
            )

    if xhs_quota_exceeded:
        logger.warning(
            "XHS API quota exhausted during inspiration collection (%d/%d calls used)",
            calls_used,
            max_calls,
        )

    state = state.append_trace(
        "Inspiration",
        f"collected {len(inspirations)} reference note(s), {calls_used} API call(s)",
    )
    inspirations = _ensure_notes_per_day(
        inspirations,
        days,
        trip.destination,
        target_per_day=max_notes,
    )
    return state.model_copy(
        update={"outfit_inspirations": inspirations, "xhs_query_debug": query_debug}
    )


def _ensure_notes_per_day(
    inspirations: list[OutfitInspiration],
    days: list[DayItinerary],
    destination: str,
    *,
    target_per_day: int,
) -> list[OutfitInspiration]:
    if not days or target_per_day <= 0:
        return inspirations

    by_date: dict = {}
    for ref in inspirations:
        by_date.setdefault(ref.trip_date, []).append(ref)

    normalized: list[OutfitInspiration] = []

    for row in days:
        day_refs: list[OutfitInspiration] = []
        seen_ids: set[str] = set()
        for ref in sorted(
            by_date.get(row.date, []),
            key=lambda item: item.liked_count or 0,
            reverse=True,
        ):
            if ref.note_id in seen_ids:
                continue
            seen_ids.add(ref.note_id)
            day_refs.append(ref)
            if len(day_refs) >= target_per_day:
                break
        if len(day_refs) >= target_per_day:
            normalized.extend(day_refs[:target_per_day])

    return normalized


_backfill_missing_day_inspirations = _ensure_notes_per_day
