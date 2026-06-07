from datetime import date

from src.graph.state import NoteOutfitAnalysis, OutfitInspiration
from src.services.trend_analysis import aggregate_day_trend


def test_aggregate_day_trend_ranks_popular_items() -> None:
    day = date(2026, 7, 10)
    analyses = [
        NoteOutfitAnalysis(
            note_id="a",
            style="韩系极简",
            top="灰色短款针织",
            bottom="白色高腰阔腿裤",
            shoes="德训鞋",
            color_palette="灰白黑",
            image_prompt_en="A young woman in clean girl style.",
        ),
        NoteOutfitAnalysis(
            note_id="b",
            style="韩系极简",
            top="灰色短款针织",
            bottom="牛仔裤",
            shoes="德训鞋",
        ),
    ]
    inspirations = [
        OutfitInspiration(
            trip_date=day,
            note_id="a",
            title="东京穿搭",
            liked_count=23000,
        ),
        OutfitInspiration(
            trip_date=day,
            note_id="b",
            title="东京拍照",
            liked_count=9000,
        ),
    ]
    trend = aggregate_day_trend(
        day,
        analyses,
        inspirations,
        destination="东京",
        spot_name="浅草寺",
        gender="女",
    )

    assert trend.dominant_style == "韩系极简"
    assert trend.top_picks[0] == "灰色短款针织"
    assert "白色高腰阔腿裤" in trend.bottom_picks
    assert trend.shoes_picks[0] == "德训鞋"
    assert "clean girl" in trend.editorial_prompt_en.lower()
