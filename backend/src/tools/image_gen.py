"""Outfit look image generation — Jimeng (Volcengine) primary, DashScope fallback."""

from __future__ import annotations

import time
from pathlib import Path

import httpx

from src.config import get_settings
from src.tools.jimeng import generate_jimeng_image

DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/api/v1"
IMAGE_SYNTHESIS_URL = f"{DASHSCOPE_BASE_URL}/services/aigc/text2image/image-synthesis"
PROMPT_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "prompts" / "image.md"

DEFAULT_NEGATIVE_PROMPT = (
    "cartoon, anime, 3d render, illustration, flat lay, mannequin, "
    "text, logo, watermark, brand name, low quality, blurry face close-up"
)
POLL_INTERVAL_SECONDS = 2.0
MAX_POLL_ATTEMPTS = 60


def load_image_prompt_template() -> str:
    return PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")


def _activities_to_scene(activities: list[str] | None) -> str:
    if not activities:
        return "popular tourist area"
    scene_map = {
        "拍照": "scenic photo spot with beautiful background",
        "逛街": "vibrant shopping street",
        "徒步": "nature trail with mountains or forest",
        "观光": "city landmark and cultural district",
        "美食": "lively local food street",
        "海边": "seaside promenade or beach",
        "露营": "outdoor campsite with natural scenery",
    }
    for activity in activities:
        if activity in scene_map:
            return scene_map[activity]
    return "popular tourist area"


def build_outfit_prompt(
    *,
    destination: str,
    date: str,
    weather_summary: str,
    outfit_summary: str,
    style: str = "休闲",
    gender: str | None = None,
    activities: list[str] | None = None,
    spot_name: str | None = None,
) -> str:
    """Build a realistic travel outfit photo prompt from trip/outfit context."""
    template = load_image_prompt_template()
    gender_text = gender or "年轻"
    spot = spot_name or destination
    from src.tools.scenic_scene import resolve_spot_scene

    spot_scene = resolve_spot_scene(spot, destination)
    return template.format(
        destination=destination,
        date=date,
        weather_summary=weather_summary,
        outfit_summary=outfit_summary,
        style=style,
        gender=gender_text,
        scene_description=_activities_to_scene(activities),
        spot_scene=spot_scene,
        spot_name=spot,
    )


def _generate_dashscope_look(prompt: str) -> str | None:
    settings = get_settings()
    if not settings.dashscope_api_key:
        return None

    try:
        with httpx.Client(timeout=30.0) as client:
            task_id = _create_dashscope_task(
                client,
                prompt=prompt,
                model=settings.image_model,
                api_key=settings.dashscope_api_key,
            )
            return _poll_dashscope_task(client, task_id, settings.dashscope_api_key)
    except (httpx.HTTPError, TimeoutError, ValueError):
        return None


def _create_dashscope_task(client: httpx.Client, prompt: str, model: str, api_key: str) -> str:
    response = client.post(
        IMAGE_SYNTHESIS_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        },
        json={
            "model": model,
            "input": {
                "prompt": prompt,
                "negative_prompt": DEFAULT_NEGATIVE_PROMPT,
            },
            "parameters": {
                "size": "1024*1024",
                "n": 1,
            },
        },
    )
    response.raise_for_status()
    payload = response.json()
    task_id = payload.get("output", {}).get("task_id")
    if not task_id:
        code = payload.get("code") or "unknown"
        message = payload.get("message") or payload
        msg = f"DashScope task creation failed ({code}): {message}"
        raise ValueError(msg)
    return task_id


def _poll_dashscope_task(client: httpx.Client, task_id: str, api_key: str) -> str | None:
    task_url = f"{DASHSCOPE_BASE_URL}/tasks/{task_id}"
    headers = {"Authorization": f"Bearer {api_key}"}

    for _ in range(MAX_POLL_ATTEMPTS):
        response = client.get(task_url, headers=headers)
        response.raise_for_status()
        payload = response.json()
        output = payload.get("output") or {}
        status = output.get("task_status")

        if status == "SUCCEEDED":
            results = output.get("results") or []
            if results and results[0].get("url"):
                return str(results[0]["url"])
            return None

        if status == "FAILED":
            message = output.get("message") or "image generation failed"
            raise ValueError(message)

        time.sleep(POLL_INTERVAL_SECONDS)

    msg = f"DashScope task timed out: {task_id}"
    raise TimeoutError(msg)


def generate_outfit_look(prompt: str) -> str | None:
    """
    Generate an outfit look image and return its URL.

    Uses Jimeng (Volcengine) when configured, otherwise falls back to DashScope.
    Returns None on failure instead of raising, so callers can degrade gracefully.
    """
    settings = get_settings()
    provider = settings.image_provider.lower()

    if provider in {"jimeng", "volcengine"}:
        url = generate_jimeng_image(prompt)
        if url:
            return url
        if provider == "jimeng":
            return None

    if provider == "dashscope" or settings.dashscope_api_key:
        return _generate_dashscope_look(prompt)

    return None
