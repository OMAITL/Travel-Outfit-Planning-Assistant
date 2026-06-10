"""FastAPI entry — serves JSON API for the Vue frontend."""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import src.graph  # noqa: F401 — PlanningState.model_rebuild()
from api.schemas import (
    ApiRecordingDetail,
    ApiRecordingListResponse,
    ApiRecordingSummary,
    CatalogResponse,
    CityOut,
    PlanRequest,
    PlanResponse,
    SpotOut,
    TripFormIn,
)
from src.services.api_recorder import get_recording, list_recordings
from app.data.city_spots import CITY_CATALOG, CITY_KEYS
from app.utils.trip_message import build_trip_context, build_trip_message
from src.config import reload_settings
from src.graph.state import InputMode, PlanningPhase, PlanningState
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


@app.get("/api/recordings", response_model=ApiRecordingListResponse)
def api_list_recordings(
    provider: str | None = Query(
        default=None,
        description="taobao_onebound | taobao_justone | xhs_justone | jimeng | deepseek",
    ),
    limit: int = Query(default=50, ge=1, le=200),
) -> ApiRecordingListResponse:
    """List recent API request/response recordings (newest first)."""
    rows = list_recordings(provider=provider, limit=limit)
    return ApiRecordingListResponse(
        items=[ApiRecordingSummary.model_validate(row) for row in rows],
        count=len(rows),
    )


@app.get("/api/recordings/{record_id}", response_model=ApiRecordingDetail)
def api_get_recording(record_id: str) -> ApiRecordingDetail:
    """Fetch one recorded API exchange by id."""
    row = get_recording(record_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Recording not found")
    return ApiRecordingDetail.model_validate(row)


_PROXY_ALLOWED_SUFFIXES = (
    "xhscdn.com",
    "xiaohongshu.com",
    "alicdn.com",
    "tbcdn.cn",
    "taobaocdn.com",
    "tmall.com",
    "tmall.hk",
    "1688.com",
    "volces.com",
    "volccdn.com",
    "byteimg.com",
)

_PROXY_REFERERS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("taobao.com", "tmall.com", "alicdn.com", "tbcdn.cn", "taobaocdn.com", "1688.com"), "https://www.taobao.com/"),
    (("xhscdn.com", "xiaohongshu.com"), "https://www.xiaohongshu.com/"),
)


def _proxy_url_allowed(url: str) -> bool:
    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        return False
    host = host.lower()
    return any(host == suffix or host.endswith(f".{suffix}") for suffix in _PROXY_ALLOWED_SUFFIXES)


def _proxy_referer_for(url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return "https://www.taobao.com/"
    for suffixes, referer in _PROXY_REFERERS:
        if any(host == suffix or host.endswith(f".{suffix}") for suffix in suffixes):
            return referer
    return "https://www.taobao.com/"


@app.get("/api/proxy-image")
def proxy_image(url: str = Query(..., min_length=8)) -> Response:
    """Proxy external CDN images (XHS / Taobao / Jimeng) to avoid browser hotlink blocks."""
    if not url.startswith(("http://", "https://")) or not _proxy_url_allowed(url):
        raise HTTPException(status_code=400, detail="Image URL not allowed")

    referer = _proxy_referer_for(url)
    try:
        with httpx.Client(timeout=httpx.Timeout(15.0), follow_redirects=True) as client:
            upstream = client.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Referer": referer,
                    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                },
            )
            upstream.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Image fetch failed: {exc}") from exc

    content_type = upstream.headers.get("content-type") or "image/jpeg"
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=502, detail="Upstream response is not an image")

    return Response(
        content=upstream.content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


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
        destination=form.destination,
        plan_mode=form.plan_mode,
        daily_spot_names=form.daily_spot_names or None,
    )
    initial = PlanningState(
        trip=ctx,
        itinerary=itinerary,
        phase=PlanningPhase.PLANNING,
        input_mode="form",
    )
    return message, initial


def _resolve_input_mode(
    body: PlanRequest,
    prior: PlanningState | None,
) -> InputMode:
    if body.trip is not None:
        return "form"
    if prior is not None and prior.input_mode:
        return prior.input_mode
    return "chat"


def _with_input_mode(state: PlanningState | None, mode: InputMode) -> PlanningState:
    if state is None:
        return PlanningState(input_mode=mode)
    return state.model_copy(update={"input_mode": mode})


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

    input_mode = _resolve_input_mode(body, prior)
    initial = _with_input_mode(initial, input_mode)

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
