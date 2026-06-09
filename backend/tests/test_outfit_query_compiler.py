"""Tests for Outfit Query Compiler."""

from datetime import date

from src.graph.state import TripPreferences
from src.services.outfit_query_compiler import (
    OutfitQueryCompiler,
    SearchTier,
    compile_level1_spot_queries,
    compile_level2_scene_queries,
    compile_outfit_query,
    compile_tiered_search_ladder,
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
    assert compiled.final_query == "洱海 女生 小个子 梨形 休闲 穿搭"
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
    assert queries[0] == "洱海 穿搭"
    assert any("洱海 女生 高个子 H型 韩系 穿搭" == q for q in queries)


def test_note_rejected_by_semantic_negative() -> None:
    prefs = TripPreferences(avoid_items=["不想太暴露"])
    profile = profile_from_preferences(prefs, destination="大理", spot="洱海")
    note = XhsNoteSummary(
        note_id="1",
        title="海边比基尼穿搭分享",
        cover_url="https://xhs.example/c.jpg",
    )
    assert note_rejected_by_profile(note, profile) is not None


def test_level1_includes_outfit_suffix_variants() -> None:
    prefs = TripPreferences(gender="女", style="简约", body_type="微胖", height_cm=165, weight_kg=75)
    profile = profile_from_preferences(
        prefs,
        destination="大理",
        spot="洱海生态廊道",
        trip_date=date(2026, 6, 9),
    )
    queries = [q for q, tier in compile_level1_spot_queries(profile)]
    assert queries[0] == "洱海 女生 微胖女生 大码女生 简约 穿搭"
    assert len(queries) > 1
    assert all("洱海" in q for q in queries)


def test_level2_scene_fallback_for_kuanzhai() -> None:
    prefs = TripPreferences(gender="女", style="韩系")
    profile = profile_from_preferences(
        prefs,
        destination="成都",
        spot="宽窄巷子",
        trip_date=date(2026, 6, 10),
    )
    scene_queries = [q for q, tier in compile_level2_scene_queries(profile)]
    assert any("古镇" in q for q in scene_queries)


def test_tiered_ladder_order_spot_before_city() -> None:
    prefs = TripPreferences(gender="女", style="休闲")
    profile = profile_from_preferences(
        prefs,
        destination="成都",
        spot="宽窄巷子",
        trip_date=date(2026, 6, 10),
    )
    ladder = compile_tiered_search_ladder(profile)
    tiers = [tier for _q, tier in ladder]
    if SearchTier.SPOT in tiers and SearchTier.CITY in tiers:
        assert tiers.index(SearchTier.SPOT) < tiers.index(SearchTier.CITY)


def test_photogenic_style_uses_broad_queries_not_literal_tag() -> None:
    from src.services.outfit_query_compiler import compile_broad_spot_queries
    from src.services.xhs_keywords import pick_xhs_style_for_search

    assert pick_xhs_style_for_search(["拍照出片"]) == "出片"
    assert pick_xhs_style_for_search(["拍照出片", "文艺"]) == "文艺"

    prefs = TripPreferences(gender="女", style="拍照出片", body_type="梨型")
    profile = profile_from_preferences(
        prefs,
        destination="大理",
        spot="大理古城",
        trip_date=date(2026, 6, 9),
    )
    broad = [q for q, _ in compile_broad_spot_queries(profile)]
    assert broad[0] == "大理古城 穿搭"
    assert all("拍照出片" not in q for q in broad)


def test_profile_negative_constraints_from_avoid_items() -> None:
    prefs = TripPreferences(avoid_items=["不穿裙子", "拒穿牛仔"])
    profile = profile_from_preferences(prefs, destination="京都", spot="清水寺")
    assert "不穿裙子" in profile.negative_constraints
