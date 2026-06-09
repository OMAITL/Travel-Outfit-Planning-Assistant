from datetime import date

from src.services.xhs_keywords import (
    avoid_match_tokens,
    build_xhs_search_keywords,
    gender_search_label,
    height_search_label,
    note_hits_avoid_items,
    season_hint_for_month,
    spot_outfit_keyword,
    spot_search_label,
)
from src.tools.justone_xhs import XhsNoteSummary


def test_season_hint_for_summer() -> None:
    assert season_hint_for_month(7) == "夏季"


def test_height_search_label_thresholds() -> None:
    assert height_search_label(158) == "小个子"
    assert height_search_label(165) == ""
    assert height_search_label(172) == "高个子"


def test_spot_search_label_shortens_formal_names() -> None:
    assert spot_search_label("洱海生态廊道", "大理") == "洱海"
    assert spot_search_label("大理古城", "大理") == "大理古城"
    assert spot_search_label("喜洲古镇", "大理") == "喜洲"


def test_spot_outfit_keyword_combines_profile() -> None:
    keyword = spot_outfit_keyword(
        "洱海生态廊道",
        gender="女",
        style="休闲",
        body_type="梨型",
        height_cm=158,
    )
    assert keyword == "洱海 女生 小个子 梨形 休闲 穿搭"


def test_spot_outfit_keyword_skips_unlimited_body_type() -> None:
    keyword = spot_outfit_keyword("大理古城", gender="女", body_type="不限", height_cm=165)
    assert keyword == "大理古城 女生 休闲 穿搭" or keyword == "大理古城 女生 穿搭"
    # style defaults not passed — only gender + spot
    keyword2 = spot_outfit_keyword("大理古城", gender="女", body_type="不限")
    assert keyword2 == "大理古城 女生 穿搭"


def test_build_xhs_search_keywords_one_per_spot() -> None:
    keywords = build_xhs_search_keywords(
        "大理",
        style="休闲",
        spot_names=["洱海生态廊道", "大理古城"],
        gender="女",
        body_type="H型",
        height_cm=172,
        trip_date=date(2026, 7, 10),
        max_keywords=12,
    )
    assert keywords[0] == "洱海 穿搭"
    assert any("洱海 女生 高个子 H型 休闲 穿搭" == q for q in keywords)


def test_build_xhs_search_keywords_city_fallback_without_spots() -> None:
    keywords = build_xhs_search_keywords(
        "东京",
        style="韩系",
        spot_names=[],
        gender="女",
        height_cm=155,
        trip_date=date(2026, 7, 10),
    )
    assert keywords[0] == "东京 女生 小个子 韩系 穿搭"
    assert "东京 夏季穿搭" in keywords


def test_gender_search_label() -> None:
    assert gender_search_label("女") == "女生"
    assert gender_search_label("不限") == ""


def test_note_hits_avoid_items() -> None:
    note = XhsNoteSummary(
        note_id="1",
        title="洱海拍照 白色连衣裙穿搭",
        cover_url="https://xhs.example/c.jpg",
    )
    assert note_hits_avoid_items(note, ["不穿裙子"])
    assert not note_hits_avoid_items(note, [])


def test_avoid_match_tokens_parses_prefixes() -> None:
    tokens = avoid_match_tokens(["不穿裙子", "拒穿牛仔"])
    assert "裙子" in tokens
    assert "牛仔" in tokens
