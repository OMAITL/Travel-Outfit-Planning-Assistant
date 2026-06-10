from datetime import date

import pytest
from pydantic import ValidationError

from src.graph.nodes.trip import TripExtraction


def test_trip_extraction_coerces_null_style_fields() -> None:
    raw = {
        "is_complete": False,
        "missing_fields": ["end_date"],
        "destination": "广州",
        "start_date": "2026-06-12",
        "end_date": None,
        "scene_type": None,
        "climate_hint": "广州6月湿热多雨",
        "style_tendency": None,
        "style": None,
        "activities": [],
        "follow_up_field": "dates",
        "follow_up_question": "你计划在广州待几天？",
        "follow_up_options": ["1天", "2天", "3天", "自定义"],
    }
    extraction = TripExtraction.model_validate(raw)
    assert extraction.style_tendency == ""
    assert extraction.style == "休闲"
    assert extraction.destination == "广州"
    assert extraction.start_date == date(2026, 6, 12)


def test_trip_extraction_coerces_null_party_size_and_lists() -> None:
    raw = {
        "destination": "广州",
        "start_date": "2026-06-12",
        "end_date": "2026-06-12",
        "scene_type": None,
        "climate_hint": None,
        "style_tendency": None,
        "gender": None,
        "spot_names": None,
        "budget_per_item": None,
        "budget_total": None,
        "body_type": None,
        "height_cm": None,
        "weight_kg": None,
        "skin_tone": None,
        "avoid_items": [],
        "avoid_items_acknowledged": False,
        "activities": None,
        "party_size": None,
        "is_complete": False,
        "missing_fields": ["scene_type", "gender", "spot_names", "budget", "body_type", "height_weight", "skin_tone", "avoid_items"],
        "follow_up_field": "scene_type",
        "follow_up_question": "你这次更偏向哪种穿搭场景？",
        "follow_up_options": ["出片拍照", "舒适休闲", "混合风格"],
    }
    extraction = TripExtraction.model_validate(raw)
    assert extraction.party_size == 1
    assert extraction.activities == []
    assert extraction.spot_names == []
    assert extraction.follow_up_field == "scene_type"


def test_trip_extraction_rejects_invalid_without_coercion() -> None:
    with pytest.raises(ValidationError):
        TripExtraction.model_validate({"start_date": "not-a-date"})
