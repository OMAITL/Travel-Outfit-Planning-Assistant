"""Tests for size hint inference."""

from src.services.sizing import infer_size_hint


def test_infer_size_hint_from_height_weight() -> None:
    hint = infer_size_hint(165, 55, "女")
    assert "165" in hint
    assert hint.startswith(("M", "L", "S"))
