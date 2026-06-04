"""FastAPI endpoint tests."""

from datetime import date

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

import src.graph  # noqa: F401
from api.main import app
from api.schemas import TripFormIn


client = TestClient(app)


def test_health() -> None:
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_catalog_cities() -> None:
    res = client.get("/api/catalog/cities")
    assert res.status_code == 200
    data = res.json()
    assert len(data["cities"]) >= 1
    assert data["cities"][0]["spots"]


def test_trip_form_schema_accepts_category_budgets() -> None:
    form = TripFormIn(
        destination="大理",
        start_date=date(2026, 6, 5),
        end_date=date(2026, 6, 7),
        styles=["休闲", "韩系"],
        spot_names=["洱海生态廊道"],
        budget_by_category={"top": 200, "bottom": 200, "shoes": 250, "acc": 150},
        skin_tone="自然",
        avoid_items=["不穿短裤"],
    )
    assert form.budget_by_category is not None
    assert form.budget_by_category.shoes == 250


def test_plan_requires_message_or_trip() -> None:
    res = client.post("/api/plan", json={})
    assert res.status_code == 400
