"""Debug XHS inspiration pipeline for a trip profile."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from src.graph.nodes.inspiration import _collect_day_notes_tiered, _note_passes_filters
from src.graph.state import TripPreferences
from src.services.outfit_query_compiler import (
    XhsFilterStats,
    compile_tiered_search_ladder,
    note_rejected_by_profile,
    profile_from_preferences,
)
from src.tools.justone_xhs import search_xhs_notes


def _safe(text: str, limit: int = 40) -> str:
    cleaned = text[:limit].encode("ascii", "backslashreplace").decode("ascii")
    return cleaned


def main() -> int:
    prefs = TripPreferences(
        gender="女",
        styles=["温柔"],
        height_cm=165,
        weight_kg=55,
        body_type="标准",
        spot_names=["洱海生态廊道"],
    )
    profile = profile_from_preferences(
        prefs,
        destination="大理",
        spot="洱海生态廊道",
        trip_date=date(2026, 6, 10),
    )

    print("=== Planner keywords (first 5) ===")
    for query, tier in compile_tiered_search_ladder(profile)[:5]:
        print(f"  [{tier}] {query}")

    print("\n=== Raw API + filters ===")
    stats = XhsFilterStats()
    notes = search_xhs_notes("洱海 穿搭", use_cache=True)
    print(f"API returned: {len(notes)} notes")
    passed = 0
    for note in notes[:10]:
        ok = _note_passes_filters(note, profile, min_liked=0, stats=stats)
        status = "OK" if ok else "SKIP"
        print(f"  [{status}] {_safe(note.title)} likes={note.liked_count}")
        if not ok and note_rejected_by_profile(note, profile):
            print("         rejected by profile/avoid rules")
        passed += int(ok)
    print(
        f"Filter stats: avoid={stats.avoid} non_outfit={stats.non_outfit} "
        f"low_likes={stats.low_likes} passed_in_first_10={passed}"
    )

    print("\n=== Tiered collect (same as planning node) ===")
    collected, calls, _tried, traces = _collect_day_notes_tiered(
        [profile],
        max_notes=3,
        fetch_detail=False,
        max_api_calls=5,
        min_liked=0,
        stop_after_notes=3,
    )
    print(f"Kept: {len(collected)} note(s), API calls: {calls}")
    for note, keyword in collected:
        print(f"  via [{keyword}]: {_safe(note.title, 50)}")
    for line in traces:
        print(f"  trace: {line}")

    if collected:
        print("\nOK — planning pipeline should show real note links after re-plan.")
        return 0

    print("\nFAIL — notes returned by API but filtered out or aborted in tiered collect.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
