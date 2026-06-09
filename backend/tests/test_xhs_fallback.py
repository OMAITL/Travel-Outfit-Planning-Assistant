"""Tests for XHS search fallback ladder and synthetic search links."""

from datetime import date

from src.graph.nodes.inspiration import _synthetic_search_link_inspirations
from src.graph.state import TripPreferences
from src.services.outfit_query_compiler import compile_fallback_queries, profile_from_preferences
from src.services.xhs_keywords import build_xhs_search_url


def test_compile_fallback_queries_includes_season_and_city() -> None:
    prefs = TripPreferences(gender="女", style="简约", body_type="健壮", height_cm=165, weight_kg=200)
    profile = profile_from_preferences(
        prefs,
        destination="成都",
        spot="宽窄巷子",
        trip_date=date(2026, 6, 10),
    )
    queries = compile_fallback_queries(profile)
    assert any("古镇" in q for q in queries)
    assert any(q.startswith("成都") for q in queries)
    assert any("穿搭" in q or "OOTD" in q for q in queries)


def test_build_xhs_search_url_encodes_keyword() -> None:
    url = build_xhs_search_url("宽窄巷子 女生 简约 穿搭")
    assert url.startswith("https://www.xiaohongshu.com/search_result?keyword=")
    assert "宽窄巷子" in url or "%E5%AE" in url


def test_synthetic_search_link_inspirations() -> None:
    prefs = TripPreferences(gender="女", style="简约", body_type="健壮", height_cm=165, weight_kg=200)
    links = _synthetic_search_link_inspirations(
        date(2026, 6, 10),
        destination="成都",
        spots=["宽窄巷子"],
        prefs=prefs,
        limit=3,
    )
    assert len(links) == 3
    assert all(link.is_search_link for link in links)
    assert all("xiaohongshu.com" in link.note_url for link in links)
    assert all(link.title.startswith("在小红书搜索") for link in links)
