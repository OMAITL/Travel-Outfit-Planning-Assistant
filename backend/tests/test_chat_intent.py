from datetime import date

from src.services.chat_intent import (
    ChatIntentDraft,
    apply_message_quick_replies,
    build_intent_draft,
    finalize_trip_intent,
    merge_extraction_with_draft,
    merge_quick_replies,
    normalize_scene_type,
    scene_activities,
)


def test_normalize_scene_from_quick_reply() -> None:
    assert normalize_scene_type("出片拍照") == "拍照"
    assert normalize_scene_type("舒适休闲") == "度假"
    assert normalize_scene_type("混合风格") == "混合"


def test_finalize_requires_scene_type() -> None:
    intent = finalize_trip_intent(
        destination="大理",
        start_date=None,
        end_date=None,
        scene_type=None,
        style_tendency="",
        climate_hint="早晚温差大",
        activities=[],
        style="休闲",
        is_complete=False,
        follow_up_question=None,
        follow_up_field=None,
        follow_up_options=[],
    )
    assert "start_date" in intent.missing_fields
    assert "end_date" in intent.missing_fields
    assert "scene_type" in intent.missing_fields
    assert intent.follow_up_field == "dates"
    assert intent.follow_up_options


def test_finalize_core_complete_still_requires_profile() -> None:
    intent = finalize_trip_intent(
        destination="广州",
        start_date=date(2026, 6, 12),
        end_date=date(2026, 6, 12),
        scene_type="拍照",
        style_tendency="休闲出片",
        climate_hint="湿热",
        activities=[],
        style="休闲",
        is_complete=True,
        follow_up_question=None,
        follow_up_field=None,
        follow_up_options=[],
    )
    assert not intent.is_complete
    assert intent.follow_up_field == "gender"
    assert "gender" in intent.missing_fields


def test_finalize_after_body_type_requires_height_weight() -> None:
    intent = finalize_trip_intent(
        destination="广州",
        start_date=date(2026, 6, 12),
        end_date=date(2026, 6, 12),
        scene_type="拍照",
        style_tendency="",
        climate_hint="",
        gender="女",
        spot_names=["市区闲逛"],
        budget_per_item=200.0,
        body_type="标准",
        skin_tone="自然",
        avoid_items=[],
        avoid_items_acknowledged=True,
        activities=[],
        style="休闲",
        is_complete=True,
        follow_up_question=None,
        follow_up_field=None,
        follow_up_options=[],
    )
    assert not intent.is_complete
    assert intent.follow_up_field == "height_weight"
    assert "height_weight" in intent.missing_fields
    assert intent.follow_up_options == []


def test_free_text_fields_have_no_quick_options() -> None:
    from src.services.chat_intent import default_follow_up

    for field in ("height_weight", "skin_tone", "avoid_items"):
        _, options = default_follow_up(field, destination="广州")
        assert options == [], f"{field} should not show quick-reply chips"


def test_finalize_complete_with_profile() -> None:
    intent = finalize_trip_intent(
        destination="广州",
        start_date=date(2026, 6, 12),
        end_date=date(2026, 6, 14),
        scene_type="拍照",
        style_tendency="休闲出片",
        climate_hint="湿热",
        gender="女",
        spot_names=["市区闲逛"],
        budget_per_item=200.0,
        body_type="标准",
        height_cm=165.0,
        weight_kg=55.0,
        skin_tone="自然",
        avoid_items=[],
        avoid_items_acknowledged=True,
        activities=[],
        style="休闲",
        is_complete=True,
        follow_up_question=None,
        follow_up_field=None,
        follow_up_options=[],
    )
    assert intent.is_complete
    assert intent.scene_type == "拍照"
    assert "拍照" in scene_activities(intent.scene_type)


def test_avoid_none_quick_reply_acknowledges() -> None:
    intent = finalize_trip_intent(
        destination="广州",
        start_date=date(2026, 6, 12),
        end_date=date(2026, 6, 12),
        scene_type="拍照",
        style_tendency="",
        climate_hint="",
        gender="女",
        spot_names=["广州经典景点"],
        budget_per_item=200.0,
        body_type="标准",
        height_cm=165.0,
        weight_kg=55.0,
        skin_tone="自然",
        avoid_items=["没有"],
        avoid_items_acknowledged=False,
        activities=[],
        style="休闲",
        is_complete=True,
        follow_up_question=None,
        follow_up_field=None,
        follow_up_options=[],
    )
    assert intent.avoid_items == []
    assert intent.avoid_items_acknowledged
    assert intent.is_complete


def test_chat_mode_skips_budget_requirement() -> None:
    intent = finalize_trip_intent(
        destination="广州",
        start_date=date(2026, 6, 12),
        end_date=date(2026, 6, 12),
        scene_type="拍照",
        style_tendency="",
        climate_hint="",
        gender="女",
        spot_names=["沙面岛"],
        body_type="梨型",
        height_cm=165.0,
        weight_kg=55.0,
        skin_tone="自然",
        avoid_items=[],
        avoid_items_acknowledged=True,
        activities=[],
        style="休闲",
        is_complete=True,
        follow_up_question=None,
        follow_up_field=None,
        follow_up_options=[],
        require_budget=False,
    )
    assert intent.is_complete
    assert "budget" not in intent.missing_fields


def test_merge_preserves_destination_when_llm_returns_null() -> None:
    draft = ChatIntentDraft(
        destination="广州",
        start_date=date(2026, 6, 12),
        end_date=date(2026, 6, 12),
        scene_type="拍照",
        gender="女",
    )
    merged = merge_extraction_with_draft(
        destination=None,
        start_date=None,
        end_date=None,
        scene_type=None,
        style_tendency="",
        climate_hint="",
        gender=None,
        spot_names=["沙面岛"],
        budget_per_item=None,
        budget_total=None,
        height_cm=None,
        weight_kg=None,
        body_type="梨型",
        skin_tone=None,
        avoid_items=[],
        avoid_items_acknowledged=False,
        activities=[],
        style="休闲",
        draft=draft,
    )
    assert merged["destination"] == "广州"
    assert merged["start_date"] == date(2026, 6, 12)
    assert merged["gender"] == "女"
    assert merged["spot_names"] == ["沙面岛"]


def test_apply_help_me_recommend_awaits_spot_pick() -> None:
    quick = apply_message_quick_replies("暂无，帮我推荐", destination="广州")
    assert "spot_names" not in quick
    assert quick["_awaiting_spot_pick"] is True


def test_spot_pick_shows_recommendations() -> None:
    merged = merge_quick_replies(
        {
            "destination": "广州",
            "start_date": date(2026, 6, 12),
            "end_date": date(2026, 6, 12),
            "scene_type": "拍照",
            "gender": "女",
            "spot_names": [],
            "activities": [],
            "style": "休闲",
            "avoid_items": [],
            "avoid_items_acknowledged": False,
        },
        apply_message_quick_replies("暂无，帮我推荐", destination="广州"),
    )
    intent = finalize_trip_intent(
        destination=merged["destination"],  # type: ignore[arg-type]
        start_date=merged["start_date"],  # type: ignore[arg-type]
        end_date=merged["end_date"],  # type: ignore[arg-type]
        scene_type=merged["scene_type"],  # type: ignore[arg-type]
        style_tendency="",
        climate_hint="",
        gender=merged["gender"],  # type: ignore[arg-type]
        spot_names=merged["spot_names"],  # type: ignore[arg-type]
        activities=[],
        style="休闲",
        is_complete=True,
        follow_up_question=None,
        follow_up_field=None,
        follow_up_options=[],
        require_budget=False,
        awaiting_spot_pick=True,
    )
    assert intent.follow_up_field == "spot_names"
    assert "spot_names" in intent.missing_fields
    assert intent.spot_names == []
    assert intent.awaiting_spot_pick is True
    assert "沙面岛" in intent.follow_up_options
    assert "都要" in intent.follow_up_options


def test_spot_pick_single_selection() -> None:
    quick = apply_message_quick_replies("沙面岛", destination="广州")
    assert quick["spot_names"] == ["沙面岛"]
    assert quick["_awaiting_spot_pick"] is False


def test_spot_pick_all_selection() -> None:
    quick = apply_message_quick_replies("都要", destination="广州")
    assert quick["spot_names"] == ["沙面岛", "东山口", "广州塔"]
    assert quick["_awaiting_spot_pick"] is False


def test_spot_pick_then_body_type() -> None:
    merged = merge_quick_replies(
        {
            "destination": "广州",
            "start_date": date(2026, 6, 12),
            "end_date": date(2026, 6, 12),
            "scene_type": "拍照",
            "gender": "女",
            "spot_names": [],
            "activities": [],
            "style": "休闲",
            "avoid_items": [],
            "avoid_items_acknowledged": False,
        },
        apply_message_quick_replies("东山口", destination="广州"),
    )
    intent = finalize_trip_intent(
        destination=merged["destination"],  # type: ignore[arg-type]
        start_date=merged["start_date"],  # type: ignore[arg-type]
        end_date=merged["end_date"],  # type: ignore[arg-type]
        scene_type=merged["scene_type"],  # type: ignore[arg-type]
        style_tendency="",
        climate_hint="",
        gender=merged["gender"],  # type: ignore[arg-type]
        spot_names=merged["spot_names"],  # type: ignore[arg-type]
        activities=[],
        style="休闲",
        is_complete=True,
        follow_up_question=None,
        follow_up_field=None,
        follow_up_options=[],
        require_budget=False,
        awaiting_spot_pick=False,
    )
    assert intent.follow_up_field == "body_type"
    assert intent.spot_names == ["东山口"]
    assert intent.awaiting_spot_pick is False


def test_build_intent_draft() -> None:
    intent = finalize_trip_intent(
        destination="大理",
        start_date=date(2026, 7, 10),
        end_date=date(2026, 7, 12),
        scene_type="度假",
        style_tendency="文艺",
        climate_hint="凉爽",
        gender="女",
        spot_names=["洱海"],
        budget_per_item=300.0,
        body_type="梨型",
        height_cm=158.0,
        weight_kg=52.0,
        skin_tone="偏白",
        avoid_items=[],
        avoid_items_acknowledged=True,
        activities=[],
        style="文艺",
        is_complete=True,
        follow_up_question=None,
        follow_up_field=None,
        follow_up_options=[],
    )
    draft = build_intent_draft(intent)
    assert draft.destination == "大理"
    assert draft.scene_type == "度假"
    assert draft.style_tendency == "文艺"
    assert draft.spot_names == ["洱海"]
    assert draft.height_cm == 158.0
    assert draft.weight_kg == 52.0
