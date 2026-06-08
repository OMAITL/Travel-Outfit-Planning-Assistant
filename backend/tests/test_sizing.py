"""Tests for size hint inference."""

from src.services.sizing import infer_size_hint


def test_infer_size_hint_from_height_weight() -> None:
    hint = infer_size_hint(165, 55, "女")
    assert "165" in hint
    assert hint.startswith(("M", "L", "S"))
    assert "大码" not in hint


def test_infer_size_hint_plus_size() -> None:
    hint = infer_size_hint(165, 200, "女", body_type="健壮")
    assert "大码" in hint
    assert any(size in hint for size in ("4XL", "5XL"))
