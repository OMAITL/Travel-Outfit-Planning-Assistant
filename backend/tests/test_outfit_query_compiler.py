"""Tests for Outfit Query Compiler."""

from datetime import date

from src.graph.state import TripPreferences
from src.services.outfit_query_compiler import (
    OutfitQueryCompiler,
    compile_outfit_query,
    note_rejected_by_profile,
    profile_from_preferences,
)
from src.tools.justone_xhs import XhsNoteSummary


def test_compile_outfit_query_full_profile() -> None:
    prefs = TripPreferences(
        gender="女",
        style="休闲",
        body_type="梨型",
        height_cm=158,
        avoid_items=["不穿裙子"],
    )
    profile = profile_from_preferences(
        prefs,
        destination="大理",
        spot="洱海生态廊道",
        trip_date=date(2026, 6, 9),
    )
    compiled = compile_outfit_query(profile)
    assert compiled.final_query == "洱海 小个子 女生 梨形 休闲 穿搭"
    rules = {item.rule for item in compiled.base_tokens}
    assert rules == {"景点", "身高", "性别", "体型", "风格", "固定"}


def test_compiler_one_query_per_spot() -> None:
    prefs = TripPreferences(gender="女", style="韩系", height_cm=172, body_type="H型")
    compiler = OutfitQueryCompiler()
    rows = compiler.compile_queries_for_spots(
        prefs,
        destination="大理",
        spots=["洱海生态廊道", "大理古城"],
        trip_date=date(2026, 6, 9),
    )
    queries = [q for q, _ in rows]
    assert queries[0] == "洱海 高个子 女生 H型 韩系 穿搭"
    assert queries[1] == "大理古城 高个子 女生 H型 韩系 穿搭"


def test_note_rejected_by_semantic_negative() -> None:
    prefs = TripPreferences(avoid_items=["不想太暴露"])
    profile = profile_from_preferences(prefs, destination="大理", spot="洱海")
    note = XhsNoteSummary(
        note_id="1",
        title="海边比基尼穿搭分享",
        cover_url="https://xhs.example/c.jpg",
    )
    assert note_rejected_by_profile(note, profile) is not None


def test_profile_negative_constraints_from_avoid_items() -> None:
    prefs = TripPreferences(avoid_items=["不穿裙子", "拒穿牛仔"])
    profile = profile_from_preferences(prefs, destination="京都", spot="清水寺")
    assert "不穿裙子" in profile.negative_constraints
