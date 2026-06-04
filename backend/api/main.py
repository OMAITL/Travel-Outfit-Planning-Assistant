"""FastAPI entry — serves JSON API for the Vue frontend."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import src.graph  # noqa: F401 — PlanningState.model_rebuild()
from api.schemas import CatalogResponse, CityOut, PlanRequest, PlanResponse, SpotOut, TripFormIn
from app.data.city_spots import CITY_CATALOG, CITY_KEYS
from app.utils.trip_message import build_trip_context, build_trip_message
from src.config import reload_settings
from src.graph.state import PlanningPhase, PlanningState
from src.graph.workflow import run_planning
from src.services.itinerary import build_itinerary

app = FastAPI(
    title="Travel Outfit Planning API",
    version="0.1.0",
    description="LangGraph planning backend for Vue UI",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:4173",
        "http://localhost:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _load_env() -> None:
    reload_settings()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/catalog/cities", response_model=CatalogResponse)
def list_cities() -> CatalogResponse:
    cities: list[CityOut] = []
    for key in CITY_KEYS:
        city = CITY_CATALOG[key]
        cities.append(
            CityOut(
                key=city.key,
                name=city.name,
                spots=[
                    SpotOut(id=s.id, emoji=s.emoji, name=s.name, tag=s.tag) for s in city.spots
                ],
                default_spot_ids=list(city.default_spot_ids),
            )
        )
    return CatalogResponse(cities=cities)


def _message_from_trip(form: TripFormIn) -> tuple[str, PlanningState]:
    bbc = form.budget_by_category.model_dump() if form.budget_by_category else None
    message = build_trip_message(
        destination=form.destination,
        start_date=form.start_date,
        end_date=form.end_date,
        gender=form.gender,
        styles=form.styles,
        activities=form.activities,
        budget_per_item=form.budget_per_item,
        budget_total=form.budget_total,
        budget_by_category=bbc,
        height_cm=form.height_cm,
        weight_kg=form.weight_kg,
        body_type=form.body_type,
        skin_tone=form.skin_tone,
        avoid_items=form.avoid_items,
    )
    if form.spot_names:
        message = f"{message}，景点：{'、'.join(form.spot_names)}"
    ctx = build_trip_context(
        destination=form.destination,
        start_date=form.start_date,
        end_date=form.end_date,
        gender=form.gender,
        styles=form.styles,
        activities=form.activities,
        spot_names=form.spot_names,
        plan_mode=form.plan_mode,
        budget_per_item=form.budget_per_item,
        budget_total=form.budget_total,
        budget_by_category=bbc,
        height_cm=form.height_cm,
        weight_kg=form.weight_kg,
        body_type=form.body_type,
        skin_tone=form.skin_tone,
        avoid_items=form.avoid_items,
    )
    itinerary = build_itinerary(
        start_date=form.start_date,
        end_date=form.end_date,
        spot_names=form.spot_names,
        plan_mode=form.plan_mode,
        daily_spot_names=form.daily_spot_names or None,
    )
    initial = PlanningState(trip=ctx, itinerary=itinerary, phase=PlanningPhase.PLANNING)
    return message, initial


@app.post("/api/plan", response_model=PlanResponse)
def plan(body: PlanRequest) -> PlanResponse:
    prior: PlanningState | None = None
    if body.state:
        try:
            prior = PlanningState.model_validate(body.state)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid state: {exc}") from exc

    message = (body.message or "").strip()
    initial: PlanningState | None = prior

    if body.trip is not None:
        trip_msg, trip_state = _message_from_trip(body.trip)
        if not message:
            message = trip_msg
        if trip_state is not None and prior is None:
            initial = trip_state
        elif trip_state is not None and prior is not None:
            initial = prior.model_copy(
                update={
                    "trip": trip_state.trip,
                    "itinerary": trip_state.itinerary,
                    "phase": PlanningPhase.PLANNING,
                }
            )

    if not message:
        raise HTTPException(status_code=400, detail="message or trip is required")

    try:
        result = run_planning(message, state=initial)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=504,
            detail="外部 API 响应超时（万邦/即梦/天气等），请稍后重试",
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return PlanResponse(state=result)


FRONTEND_DIST = BACKEND_ROOT.parent / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
