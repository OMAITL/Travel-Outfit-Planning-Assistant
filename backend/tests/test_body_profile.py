"""Tests for body profile sizing and prompt hints."""

from src.services.body_profile import BodyProfile, infer_size_hint
from src.services.taobao_keyword import build_item_search_keyword
from src.services.xhs_keywords import spot_outfit_keyword
from src.tools.image_gen import build_outfit_prompt


def test_infer_size_hint_heavyweight_user() -> None:
    hint = infer_size_hint(165, 200, "女", body_type="健壮")
    assert "5XL" in hint or "4XL" in hint
    assert "165" in hint
    assert "大码" in hint
    assert "加肥加大" in hint


def test_infer_size_hint_normal_weight() -> None:
    hint = infer_size_hint(165, 55, "女")
    assert "165" in hint
    assert "大码" not in hint


def test_body_profile_image_subject_plus_size() -> None:
    profile = BodyProfile(
        height_cm=165,
        weight_kg=200,
        body_type="健壮",
        skin_tone="小麦色",
        gender="女",
    )
    subject = profile.image_subject_zh()
    assert "165" in subject
    assert "200" in subject
    assert "小麦色" in subject
    assert "健壮" in subject
    assert "大码" in subject or "丰满" in subject
    assert profile.image_negative_extra()
    assert "极瘦" in profile.image_negative_extra()


def test_build_outfit_prompt_reflects_body_profile() -> None:
    prompt = build_outfit_prompt(
        destination="三亚",
        date="2026-07-10",
        weather_summary="晴, 28~34°C",
        outfit_summary="上装：珊瑚粉吊带长裙 | 鞋：人字拖",
        style="海岛风",
        gender="女",
        height_cm=165,
        weight_kg=200,
        body_type="健壮",
        skin_tone="小麦色",
        activities=["海边"],
        spot_name="亚龙湾",
    )
    assert "200" in prompt
    assert "小麦色" in prompt
    assert "【人物体型】" in prompt
    assert "极瘦" in prompt
    assert "年轻女性" not in prompt


def test_taobao_keyword_includes_plus_size_tokens() -> None:
    keyword = build_item_search_keyword(
        "珊瑚粉热带印花连衣裙",
        gender="女",
        style="海岛风",
        height_cm=165,
        weight_kg=200,
        body_type="健壮",
    )
    assert "大码" in keyword
    assert "加肥加大" in keyword
    assert "珊瑚粉" in keyword


def test_xhs_spot_keyword_includes_plus_size() -> None:
    keyword = spot_outfit_keyword(
        "亚龙湾",
        destination="三亚",
        gender="女",
        style="海岛风",
        body_type="健壮",
        height_cm=165,
        weight_kg=200,
    )
    assert "大码" in keyword
    assert "健壮" in keyword
    assert "女生" in keyword
