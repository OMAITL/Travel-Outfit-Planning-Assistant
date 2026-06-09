"""Tests for the multimodal Vision Agent helpers."""

from langchain_core.messages import HumanMessage

from src.services.xhs_keywords import note_looks_non_outfit
from src.services.llm import build_image_human_message
from src.tools.justone_xhs import XhsNoteSummary


def test_build_image_human_message_mixes_text_and_images() -> None:
    msg = build_image_human_message(
        "look at these",
        ["data:image/jpeg;base64,AAAA", "https://cdn.example/x.jpg", ""],
    )
    assert isinstance(msg, HumanMessage)
    assert isinstance(msg.content, list)
    assert msg.content[0] == {"type": "text", "text": "look at these"}
    image_blocks = [b for b in msg.content if b.get("type") == "image_url"]
    # empty url skipped
    assert len(image_blocks) == 2
    assert image_blocks[0]["image_url"]["url"].startswith("data:image/jpeg")


def _note(title: str, desc: str = "") -> XhsNoteSummary:
    return XhsNoteSummary(
        note_id="n1",
        title=title,
        cover_url="https://xhs.example/c.jpg",
        desc=desc,
    )


def test_note_looks_non_outfit_rejects_routes_but_keeps_pose_notes() -> None:
    assert note_looks_non_outfit(_note("大理3日游懒人不绕路游玩攻略！！！附机位"))
    assert not note_looks_non_outfit(_note("提前预习!!!大理拍照姿势（古镇篇）"))


def test_note_looks_non_outfit_keeps_outfit_notes() -> None:
    # Has an outfit cue → kept even if it also mentions 拍照.
    assert not note_looks_non_outfit(_note("洱海边穿搭分享 ootd", desc="白色长裙拍照超出片"))
    assert not note_looks_non_outfit(_note("大理古城超适合洱海的春夏穿搭"))


def test_merge_display_inspirations_backfills_when_vision_filters_all() -> None:
    from datetime import date

    from src.graph.nodes.vision import _merge_display_inspirations
    from src.graph.state import DayItinerary, OutfitInspiration

    day = date(2026, 6, 9)
    refs = [
        OutfitInspiration(
            trip_date=day,
            note_id="a",
            title="洱海穿搭",
            cover_url="https://xhs.example/1.jpg",
            note_url="https://xhs.example/a",
            liked_count=1000,
        ),
        OutfitInspiration(
            trip_date=day,
            note_id="b",
            title="古城穿搭",
            cover_url="https://xhs.example/2.jpg",
            note_url="https://xhs.example/b",
            liked_count=800,
        ),
    ]
    merged = _merge_display_inspirations(
        refs,
        outfit_note_ids=set(),
        days=[DayItinerary(date=day, spot_names=["洱海"])],
        target_per_day=3,
    )
    assert len(merged) == 2
    assert {item.note_id for item in merged} == {"a", "b"}


def test_merge_display_inspirations_prefers_vision_confirmed() -> None:
    from datetime import date

    from src.graph.nodes.vision import _merge_display_inspirations
    from src.graph.state import DayItinerary, OutfitInspiration

    day = date(2026, 6, 9)
    refs = [
        OutfitInspiration(
            trip_date=day,
            note_id="a",
            title="low",
            cover_url="https://xhs.example/1.jpg",
            note_url="https://xhs.example/a",
            liked_count=100,
        ),
        OutfitInspiration(
            trip_date=day,
            note_id="b",
            title="high outfit",
            cover_url="https://xhs.example/2.jpg",
            note_url="https://xhs.example/b",
            liked_count=50,
        ),
    ]
    merged = _merge_display_inspirations(
        refs,
        outfit_note_ids={"b"},
        days=[DayItinerary(date=day, spot_names=["洱海"])],
        target_per_day=2,
    )
    assert merged[0].note_id == "b"


def test_analysis_shows_outfit_accepts_pose_note_with_garments() -> None:
    from src.graph.nodes.vision import _analysis_shows_outfit
    from src.graph.state import NoteOutfitAnalysis

    pose_note = NoteOutfitAnalysis(
        note_id="pose1",
        is_outfit=False,
        top="白色T恤",
        bottom="牛仔裤",
    )
    assert _analysis_shows_outfit(pose_note)

    scenery = NoteOutfitAnalysis(note_id="s1", is_outfit=False)
    assert not _analysis_shows_outfit(scenery)
