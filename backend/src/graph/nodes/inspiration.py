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
    compile_broad_spot_queries,
    compile_fallback_queries,
    compile_level1_spot_queries,
    compile_level2_scene_queries,
    compile_level3_city_queries,
    compile_level4_body_style_queries,
    note_rejected_by_profile,
    profile_from_preferences,
)
from src.services.xhs_keywords import build_xhs_search_url, note_looks_non_outfit
from src.tools.justone_client import JustOneApiError
from src.tools.justone_xhs import XhsNoteSummary, get_xhs_note_detail, search_xhs_notes

logger = logging.getLogger(__name__)

_MAX_DETAIL_FETCHES_PER_KEYWORD = 3

_TIER_SEARCH_STEPS: tuple[tuple[str, object], ...] = (
    ("一级-景点宽泛", compile_broad_spot_queries),
    ("一级-景点", compile_level1_spot_queries),
    ("二级-场景", compile_level2_scene_queries),
    ("三级-城市", compile_level3_city_queries),
    ("四级-身材风格", compile_level4_body_style_queries),
)


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
    if note_looks_non_outfit(note):
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
            continue
        calls += 1

        detail_fetches = 0
        for candidate in candidates:
            if len(merged) >= max_notes or calls >= max_api_calls:
                break
            if candidate.note_id in excluded or candidate.note_id in merged:
                continue
            if not _note_passes_filters(candidate, profile, min_liked=min_liked, stats=stats[spot_key]):
                continue

            note = candidate
            if (
                fetch_detail
                and calls < max_api_calls
                and detail_fetches < _MAX_DETAIL_FETCHES_PER_KEYWORD
            ):
                try:
                    detailed = get_xhs_note_detail(candidate.note_id)
                    calls += 1
                    detail_fetches += 1
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


def _profiles_for_day_spots(
    *,
    destination: str,
    spots: list[str],
    prefs,
    trip_date,
) -> list[OutfitSearchProfile]:
    spot_list = [spot.strip() for spot in spots if spot.strip()] or [destination]
    return [
        profile_from_preferences(
            prefs,
            destination=destination,
            spot=spot,
            trip_date=trip_date,
        )
        for spot in spot_list
    ]


def _collect_day_notes_tiered(
    profiles: list[OutfitSearchProfile],
    *,
    max_notes: int,
    fetch_detail: bool,
    max_api_calls: int,
    min_liked: int,
    exclude_note_ids: set[str] | None = None,
    stats_by_spot: dict[str, XhsFilterStats] | None = None,
    tried_keywords: set[str] | None = None,
    stop_after_notes: int | None = None,
) -> tuple[list[tuple[XhsNoteSummary, str]], int, set[str], list[str]]:
    """
    Run backup rules tier-by-tier (景点宽泛 → 景点 → 场景 → 城市 → 身材).

    Stops escalating to the next tier once ``stop_after_notes`` is reached so
    broader fallbacks are not skipped due to API budget exhaustion on strict queries.
    """
    tried = set(tried_keywords or ())
    tier_traces: list[str] = []
    collected: list[tuple[XhsNoteSummary, str]] = []
    calls = 0
    stop_target = stop_after_notes if stop_after_notes is not None else max_notes

    for tier_label, tier_fn in _TIER_SEARCH_STEPS:
        if calls >= max_api_calls or len(collected) >= max_notes:
            break
        if len(collected) >= stop_target:
            break

        tier_plan: list[tuple[str, OutfitSearchProfile]] = []
        for profile in profiles:
            for query, _tier in tier_fn(profile):
                if query in tried:
                    continue
                tried.add(query)
                tier_plan.append((query, profile))

        if not tier_plan:
            continue

        notes, used = _collect_day_notes(
            tier_plan,
            max_notes=max_notes - len(collected),
            fetch_detail=fetch_detail,
            max_api_calls=max_api_calls - calls,
            min_liked=min_liked,
            exclude_note_ids=exclude_note_ids,
            stats_by_spot=stats_by_spot,
        )
        calls += used
        collected.extend(notes)
        tier_traces.append(
            f"{tier_label}: +{len(notes)} note(s) from {len(tier_plan)} query(ies), {used} call(s)"
        )

    seen_ids: set[str] = set()
    ranked: list[tuple[XhsNoteSummary, str]] = []
    for note, keyword in sorted(
        collected,
        key=lambda pair: pair[0].liked_count or 0,
        reverse=True,
    ):
        if note.note_id in seen_ids:
            continue
        seen_ids.add(note.note_id)
        ranked.append((note, keyword))
        if len(ranked) >= max_notes:
            break
    return ranked, calls, tried, tier_traces


def _append_inspiration(
    inspirations: list[OutfitInspiration],
    *,
    trip_date,
    note: XhsNoteSummary,
    search_keyword: str,
    assigned_ids: set[str],
) -> bool:
    if note.note_id in assigned_ids:
        return False
    assigned_ids.add(note.note_id)
    inspirations.append(
        OutfitInspiration(
            trip_date=trip_date,
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
    return True


def _synthetic_search_link_inspirations(
    trip_date,
    *,
    destination: str,
    spots: list[str],
    prefs,
    limit: int = 3,
) -> list[OutfitInspiration]:
    """When API search finds nothing, offer clickable XHS search queries instead."""
    keywords: list[str] = []
    seen: set[str] = set()
    spot_list = [spot.strip() for spot in spots if spot.strip()] or [destination]

    for spot in spot_list:
        profile = profile_from_preferences(
            prefs,
            destination=destination,
            spot=spot,
            trip_date=trip_date,
        )
        for keyword in compile_fallback_queries(profile):
            if keyword not in seen:
                seen.add(keyword)
                keywords.append(keyword)
            if len(keywords) >= limit:
                break
        if len(keywords) >= limit:
            break

    links: list[OutfitInspiration] = []
    for index, keyword in enumerate(keywords[:limit]):
        links.append(
            OutfitInspiration(
                trip_date=trip_date,
                note_id=f"search:{trip_date}:{index}",
                title=f"在小红书搜索「{keyword}」",
                desc="未找到直接匹配的笔记，点击跳转小红书搜索结果页自行浏览参考。",
                note_url=build_xhs_search_url(keyword),
                search_keyword=keyword,
                is_search_link=True,
            )
        )
    return links


def _run_api_fallback_ladder(
    *,
    trip_date,
    destination: str,
    spots: list[str],
    prefs,
    inspirations: list[OutfitInspiration],
    assigned_ids: set[str],
    max_notes: int,
    fetch_detail: bool,
    max_api_calls: int,
    min_liked: int,
    tried_keywords: set[str] | None = None,
) -> tuple[int, int, list[str]]:
    """Continue tiered API search with queries not yet tried (incl. lower-priority tiers)."""
    if max_api_calls <= 0:
        return 0, 0, []

    day_count = len([r for r in inspirations if r.trip_date == trip_date])
    if day_count >= max_notes:
        return 0, 0, []

    profiles = _profiles_for_day_spots(
        destination=destination,
        spots=spots,
        prefs=prefs,
        trip_date=trip_date,
    )
    stats: dict[str, XhsFilterStats] = defaultdict(XhsFilterStats)
    try:
        notes, used, _tried, traces = _collect_day_notes_tiered(
            profiles,
            max_notes=max_notes - day_count,
            fetch_detail=fetch_detail,
            max_api_calls=max_api_calls,
            min_liked=min_liked,
            exclude_note_ids=assigned_ids,
            stats_by_spot=stats,
            tried_keywords=tried_keywords,
            stop_after_notes=max_notes - day_count,
        )
    except JustOneApiError:
        return 0, 0, []

    added = 0
    for note, search_keyword in notes:
        if len([r for r in inspirations if r.trip_date == trip_date]) >= max_notes:
            break
        if _append_inspiration(
            inspirations,
            trip_date=trip_date,
            note=note,
            search_keyword=search_keyword,
            assigned_ids=assigned_ids,
        ):
            added += 1
    return added, used, traces


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


def _compile_by_spot_for_day(
    *,
    compiler: OutfitQueryCompiler,
    trip,
    prefs,
    trip_date,
    day_spots: list[str],
) -> dict[str, object]:
    return {
        spot: compiler.compile(
            profile_from_preferences(
                prefs,
                destination=trip.destination,
                spot=spot,
                trip_date=trip_date,
            )
        )
        for spot in day_spots
    }


def _append_day_query_debug(
    state: PlanningState,
    query_debug: list[XhsQueryDebugEntry],
    *,
    trip_date,
    day_spots: list[str],
    compiled_by_spot: dict[str, object],
    stats_by_spot: dict[str, XhsFilterStats],
    notes_by_spot: dict[str, int],
) -> PlanningState:
    """Always record compiler debug rows so the report UI can show XHS diagnostics."""
    for spot in day_spots:
        compiled = compiled_by_spot.get(spot)
        if compiled is None:
            continue
        entry = _debug_entry_from_compile(
            trip_date,
            compiled,
            stats_by_spot.get(spot, XhsFilterStats()),
            notes_by_spot.get(spot, 0),
        )
        query_debug.append(entry)
        token_summary = " · ".join(f"{t['rule']}:{t['token']}" for t in entry.base_tokens)
        state = state.append_trace(
            "QueryCompiler",
            f"{trip_date} @{spot} →「{entry.final_query}」"
            f" | 规则[{token_summary}]"
            f" | 过滤(雷点{entry.filtered_avoid}/非穿搭{entry.filtered_non_outfit})"
            f" | 保留{entry.notes_kept}条",
        )
    return state


def _query_debug_for_trip_days(
    days: list[DayItinerary],
    *,
    trip,
    prefs,
    compiler: OutfitQueryCompiler | None = None,
) -> list[XhsQueryDebugEntry]:
    compiler = compiler or OutfitQueryCompiler()
    rows: list[XhsQueryDebugEntry] = []
    for row in days:
        day_spots = day_all_spots(row) or prefs.spot_names or [trip.destination]
        compiled_by_spot = _compile_by_spot_for_day(
            compiler=compiler,
            trip=trip,
            prefs=prefs,
            trip_date=row.date,
            day_spots=day_spots,
        )
        notes_by_spot: dict[str, int] = defaultdict(int)
        for spot in day_spots:
            entry = _debug_entry_from_compile(
                row.date,
                compiled_by_spot[spot],
                XhsFilterStats(),
                notes_by_spot.get(spot, 0),
            )
            rows.append(entry)
    return rows


def _synthetic_links_for_trip(
    days: list[DayItinerary],
    *,
    destination: str,
    prefs,
    limit_per_day: int = 3,
) -> list[OutfitInspiration]:
    """Offline fallback: tiered search keywords as clickable XHS deep-links."""
    links: list[OutfitInspiration] = []
    for row in days:
        day_spots = day_all_spots(row) or prefs.spot_names or [destination]
        links.extend(
            _synthetic_search_link_inspirations(
                row.date,
                destination=destination,
                spots=day_spots,
                prefs=prefs,
                limit=limit_per_day,
            )
        )
    return links


def inspiration_node(state: PlanningState) -> PlanningState:
    if state.trip is None or not state.trip.is_complete:
        return state.append_trace("Inspiration", "skipped: trip not ready", level="warning")

    settings = get_settings()
    trip = state.trip
    prefs = trip.preferences
    days = _planning_days(state)
    if not days:
        return state.append_trace("Inspiration", "skipped: no trip days", level="warning")

    if not settings.justoneapi_token:
        synthetic = _synthetic_links_for_trip(
            days,
            destination=trip.destination,
            prefs=prefs,
            limit_per_day=settings.justoneapi_xhs_notes_per_day,
        )
        query_debug = _query_debug_for_trip_days(days, trip=trip, prefs=prefs)
        return state.append_trace(
            "Inspiration",
            f"JUSTONEAPI_TOKEN missing — using {len(synthetic)} offline XHS search link(s)",
            level="warning",
        ).model_copy(update={"outfit_inspirations": synthetic, "xhs_query_debug": query_debug})

    display_notes = settings.justoneapi_xhs_notes_per_day
    analysis_pool = settings.justoneapi_xhs_analysis_pool_per_day
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
        f"collect up to {analysis_pool} note(s)/day for analysis, "
        f"display {display_notes}, llm_expand={settings.xhs_query_llm_expand}",
    )

    for row in days:
        if calls_used >= max_calls:
            break

        day_spots = day_all_spots(row) or prefs.spot_names or [trip.destination]
        day_profiles = _profiles_for_day_spots(
            destination=trip.destination,
            spots=day_spots,
            prefs=prefs,
            trip_date=row.date,
        )
        stats_by_spot: dict[str, XhsFilterStats] = defaultdict(XhsFilterStats)
        compiled_by_spot = _compile_by_spot_for_day(
            compiler=compiler,
            trip=trip,
            prefs=prefs,
            trip_date=row.date,
            day_spots=day_spots,
        )
        tried_keywords: set[str] = set()

        detail_budget = 1 if fetch_detail else 0
        calls_per_day = max(
            len(_TIER_SEARCH_STEPS) * max(len(day_spots), 1) + analysis_pool * (1 + detail_budget),
            max_calls // max(len(days), 1),
        )
        remaining = min(calls_per_day, max_calls - calls_used)
        if remaining <= 0:
            break
        day_assigned_ids = {r.note_id for r in inspirations if r.trip_date == row.date}
        try:
            notes, used, tried_keywords, tier_traces = _collect_day_notes_tiered(
                day_profiles,
                max_notes=analysis_pool,
                fetch_detail=fetch_detail,
                max_api_calls=remaining,
                min_liked=min_liked,
                exclude_note_ids=day_assigned_ids,
                stats_by_spot=stats_by_spot,
                stop_after_notes=display_notes,
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
            notes_by_spot: dict[str, int] = defaultdict(int)
            state = _append_day_query_debug(
                state,
                query_debug,
                trip_date=row.date,
                day_spots=day_spots,
                compiled_by_spot=compiled_by_spot,
                stats_by_spot=stats_by_spot,
                notes_by_spot=notes_by_spot,
            )
            continue

        calls_used += used
        for trace_line in tier_traces:
            state = state.append_trace("QueryCompiler", f"{row.date}: {trace_line}")
        if not tier_traces:
            state = state.append_trace(
                "QueryCompiler",
                f"{row.date}: tiered search produced no API attempts (budget exhausted?)",
                level="warning",
            )

        notes_by_spot: dict[str, int] = defaultdict(int)
        for note, search_keyword in notes:
            if note.note_id in day_assigned_ids:
                continue
            day_assigned_ids.add(note.note_id)
            matched_spot = day_spots[0]
            for profile in day_profiles:
                if profile.spot and profile.spot in search_keyword:
                    matched_spot = profile.spot
                    break
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

        state = _append_day_query_debug(
            state,
            query_debug,
            trip_date=row.date,
            day_spots=day_spots,
            compiled_by_spot=compiled_by_spot,
            stats_by_spot=stats_by_spot,
            notes_by_spot=notes_by_spot,
        )

        day_count = len([r for r in inspirations if r.trip_date == row.date])

        if day_count < display_notes and min_liked > 0 and calls_used < max_calls:
            retry_remaining = max_calls - calls_used
            try:
                retry_notes, retry_used, tried_keywords, retry_traces = _collect_day_notes_tiered(
                    day_profiles,
                    max_notes=analysis_pool - day_count,
                    fetch_detail=fetch_detail,
                    max_api_calls=retry_remaining,
                    min_liked=0,
                    exclude_note_ids=day_assigned_ids,
                    stats_by_spot=stats_by_spot,
                    tried_keywords=set(),
                    stop_after_notes=display_notes - day_count,
                )
            except JustOneApiError:
                retry_notes, retry_used, retry_traces = [], 0, []
            calls_used += retry_used
            for trace_line in retry_traces:
                state = state.append_trace(
                    "QueryCompiler",
                    f"{row.date} (放宽点赞): {trace_line}",
                )
            for note, search_keyword in retry_notes:
                if note.note_id in day_assigned_ids:
                    continue
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

        if day_count < display_notes:
            logger.warning(
                "XHS notes incomplete for %s: got %d/%d (calls_used=%d/%d, quota=%s)",
                row.date,
                day_count,
                display_notes,
                calls_used,
                max_calls,
                xhs_quota_exceeded,
            )
            remaining = max_calls - calls_used
            if remaining > 0:
                added, used, fb_traces = _run_api_fallback_ladder(
                    trip_date=row.date,
                    destination=trip.destination,
                    spots=day_spots,
                    prefs=prefs,
                    inspirations=inspirations,
                    assigned_ids=day_assigned_ids,
                    max_notes=analysis_pool,
                    fetch_detail=fetch_detail,
                    max_api_calls=remaining,
                    min_liked=0,
                    tried_keywords=tried_keywords,
                )
                calls_used += used
                for trace_line in fb_traces:
                    state = state.append_trace(
                        "QueryCompiler",
                        f"{row.date} (备用降级): {trace_line}",
                    )
                if added:
                    state = state.append_trace(
                        "Inspiration",
                        f"{row.date}: fallback ladder added {added} note(s)",
                    )
                day_count = len([r for r in inspirations if r.trip_date == row.date])

            if day_count == 0:
                synthetic = _synthetic_search_link_inspirations(
                    row.date,
                    destination=trip.destination,
                    spots=day_spots,
                    prefs=prefs,
                    limit=3,
                )
                if synthetic:
                    inspirations.extend(synthetic)
                    state = state.append_trace(
                        "Inspiration",
                        f"{row.date}: using {len(synthetic)} Xiaohongshu search link(s) as fallback",
                    )
            elif day_count < display_notes:
                state = state.append_trace(
                    "Inspiration",
                    f"{row.date}: kept {day_count} note(s) for analysis (display target {display_notes})",
                    level="warning",
                )

    if xhs_quota_exceeded:
        logger.warning(
            "XHS API quota exhausted during inspiration collection (%d/%d calls used)",
            calls_used,
            max_calls,
        )

    if not inspirations:
        inspirations = _synthetic_links_for_trip(
            days,
            destination=trip.destination,
            prefs=prefs,
            limit_per_day=display_notes,
        )
        if inspirations:
            state = state.append_trace(
                "Inspiration",
                f"no API notes — attached {len(inspirations)} offline XHS search link(s)",
                level="warning",
            )

    if not query_debug:
        query_debug = _query_debug_for_trip_days(days, trip=trip, prefs=prefs, compiler=compiler)

    state = state.append_trace(
        "Inspiration",
        f"collected {len(inspirations)} reference note(s), {calls_used} API call(s)",
    )
    inspirations = _ensure_notes_per_day(
        inspirations,
        days,
        trip.destination,
        target_per_day=analysis_pool,
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
        if day_refs:
            normalized.extend(day_refs[:target_per_day])

    return normalized


_backfill_missing_day_inspirations = _ensure_notes_per_day
