"""Outfit look image generation — Jimeng (Volcengine) primary, DashScope fallback."""

from __future__ import annotations

import time
from pathlib import Path

import httpx

from src.config import get_settings
from src.tools.jimeng import generate_jimeng_image, generate_jimeng_image_from_reference

DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/api/v1"
IMAGE_SYNTHESIS_URL = f"{DASHSCOPE_BASE_URL}/services/aigc/text2image/image-synthesis"
PROMPT_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "prompts" / "image.md"

DEFAULT_NEGATIVE_PROMPT = (
    "cartoon, anime, 3d render, illustration, flat lay, mannequin, "
    "duplicate person, twin, clone, side by side, collage, split screen, "
    "text, caption, subtitle, infographic, UI overlay, logo, watermark, brand name, "
    "low quality, blurry, overexposed, harsh flash, stiff pose, awkward proportions, "
    "distorted face, extra limbs, bad anatomy"
)
EDITORIAL_QUALITY_SUFFIX = (
    "Cinematic travel fashion photography, 85mm portrait lens, soft natural light, "
    "shallow depth of field, elegant relaxed pose, Pinterest-worthy composition, "
    "high-end magazine editorial, realistic fabric texture and natural skin tones."
)
POLL_INTERVAL_SECONDS = 2.0
MAX_POLL_ATTEMPTS = 60


def load_image_prompt_template() -> str:
    return PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")


def format_outfit_description(outfit_summary: str) -> str:
    """Strip category labels and return a clean comma-separated outfit description."""
    from app.utils.enrichment import parse_outfit_items

    parts: list[str] = []
    for _label, text in parse_outfit_items(outfit_summary):
        cleaned = text.strip().strip("。")
        if cleaned and cleaned.lower() not in {"无", "不需要", "none", "n/a", "-", "—"}:
            parts.append(cleaned)
    if parts:
        return "，".join(parts)
    return outfit_summary.replace("|", "，").replace("｜", "，").strip()


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


def _gender_subject(gender: str | None) -> str:
    value = (gender or "").strip()
    if value == "女":
        return "一位年轻女性游客"
    if value == "男":
        return "一位年轻男性游客"
    return "一位年轻游客"


def _activity_action(activities: list[str] | None) -> str:
    if not activities:
        return "在景点悠闲步行，身体放松，自然看向风景一侧"
    action_map = {
        "拍照": "在网红打卡点驻足拍照，侧身自然看向风景，姿态松弛",
        "逛街": "沿商业街缓步闲逛，轻松自在",
        "徒步": "在步道轻快行走，呼吸自然",
        "观光": "在地标前驻足观赏，微微侧身",
        "美食": "在街巷中悠闲漫步，生活感街拍",
        "海边": "在海滨步道散步，迎着微风",
        "露营": "在户外营地附近轻松站立，自然环境环绕",
    }
    for activity in activities:
        if activity in action_map:
            return action_map[activity]
    return "在景点悠闲步行，自然放松"


def _weather_atmosphere(weather_summary: str) -> str:
    summary = weather_summary.strip()
    if "雨" in summary:
        return f"当日{summary}，阴雨湿润，路面微湿反光，云层柔和"
    if "晴" in summary:
        return f"当日{summary}，阳光明媚，蓝天清透"
    if "阴" in summary or "云" in summary:
        return f"当日{summary}，多云阴天，光线柔和均匀"
    if "雪" in summary:
        return f"当日{summary}，空气清冷，地面可见薄雪"
    return f"当日天气{summary}"


def _aspect_ratio_hint() -> str:
    settings = get_settings()
    width = settings.jimeng_image_width
    height = settings.jimeng_image_height
    if height > width * 1.2:
        return "竖版3:4画幅"
    if width > height * 1.2:
        return "横版16:9画幅"
    return "方形1:1画幅"


def build_editorial_outfit_prompt(
    *,
    destination: str,
    weather_summary: str,
    outfit_summary: str,
    trend: "DayOutfitTrend | None" = None,
    style: str = "休闲",
    gender: str | None = None,
    activities: list[str] | None = None,
    spot_name: str | None = None,
    reference_hint: str = "",
) -> str:
    """Editorial i2i prompt grounded in XHS vision analysis when available."""
    from src.graph.state import DayOutfitTrend
    from src.tools.scenic_scene import resolve_spot_scene

    spot = spot_name or destination
    spot_scene = resolve_spot_scene(spot, destination)
    gender_text = gender or "young Asian woman"

    if trend and trend.editorial_prompt_en:
        base = trend.editorial_prompt_en
        outfit_desc = format_outfit_description(outfit_summary)
        photo = trend.photo_style or "instagram fashion photography, natural light"
        return (
            f"{base} Single person only, wearing exactly: {outfit_desc}. "
            f"Background: {spot_scene} at {destination} ({spot}). "
            f"Weather: {weather_summary}. Photography mood: {photo}. "
            f"{EDITORIAL_QUALITY_SUFFIX} "
            f"No duplicate people, no text, no captions, no infographic overlay, no watermark."
        )

    return build_outfit_reference_prompt(
        destination=destination,
        weather_summary=weather_summary,
        outfit_summary=outfit_summary,
        style=style,
        gender=gender,
        activities=activities,
        spot_name=spot_name,
        reference_hint=reference_hint,
    )


def build_outfit_reference_prompt(
    *,
    destination: str,
    weather_summary: str,
    outfit_summary: str,
    style: str = "休闲",
    gender: str | None = None,
    activities: list[str] | None = None,
    spot_name: str | None = None,
    reference_hint: str = "",
) -> str:
    """Prompt for Jimeng i2i — keep outfit from reference, swap in scenic background."""
    gender_text = gender or "年轻"
    spot = spot_name or destination
    from src.tools.scenic_scene import resolve_spot_scene

    spot_scene = resolve_spot_scene(spot, destination)
    outfit_desc = format_outfit_description(outfit_summary)
    hint = f" Reference note style: {reference_hint}." if reference_hint else ""
    return (
        f"Single person only, no duplicate subjects, no collage. "
        f"A {gender_text} person wearing exactly: {outfit_desc}. "
        f"Background must be {spot_scene} at {destination} ({spot}), "
        f"real tourist landmark, natural daylight travel lifestyle photo, full body mid-distance. "
        f"Weather: {weather_summary}. Style: {style}. Scene: {_activities_to_scene(activities)}."
        f"{hint} "
        f"{EDITORIAL_QUALITY_SUFFIX} "
        f"No text, captions, infographic overlay, watermark, or brand logos. Photorealistic fashion editorial."
    )


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
    """
    Build a Jimeng-optimized Chinese prompt for travel outfit look images.

    Follows official guidance: coherent natural-language scene description,
    short aesthetic tags, explicit usage and aspect ratio.
    """
    spot = spot_name or destination
    from src.tools.scenic_scene import resolve_spot_scene_zh

    subject = _gender_subject(gender)
    outfit_desc = format_outfit_description(outfit_summary)
    spot_scene = resolve_spot_scene_zh(spot, destination)
    action = _activity_action(activities)
    atmosphere = _weather_atmosphere(weather_summary)
    aspect = _aspect_ratio_hint()
    style_label = (style or "休闲").split("、")[0].strip()

    return (
        f"用于旅行穿搭方案展示的{aspect}全身时尚摄影大片，高清写实。\n\n"
        f"【画面内容】{subject}身穿{outfit_desc}，在{destination}{spot}的{spot_scene}，"
        f"{action}。{atmosphere}。\n\n"
        f"【环境】真实的{spot}旅游地标实景，{spot_scene}，可见天空与周边环境，"
        f"绝非影棚抠图或虚拟背景。\n\n"
        f"【画面美学】{style_label}风旅行穿搭摄影；自然光；清新写实配色；浅景深；"
        f"85mm人像镜头质感；中远景全身构图；面料褶皱与垂坠自然；杂志风旅拍 editorial。\n\n"
        f"【用途】旅行穿搭预览配图，{destination} {date} 行程方案展示。\n\n"
        f"仅一位人物，无拼图分屏，无文字水印，无品牌logo。"
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


def generate_outfit_look(
    prompt: str,
    *,
    reference_image_url: str | None = None,
) -> str | None:
    """
    Generate an outfit look image and return its URL.

    When reference_image_url is set and IMAGE_USE_XHS_REFERENCE is enabled, tries Jimeng
    image-to-image first (keeps XHS outfit look), then text-to-image fallback.
    """
    settings = get_settings()
    provider = settings.image_provider.lower()

    if provider in {"jimeng", "volcengine"}:
        if reference_image_url and settings.image_use_xhs_reference:
            url = generate_jimeng_image_from_reference(prompt, reference_image_url)
            if url:
                return url
        url = generate_jimeng_image(prompt)
        if url:
            return url
        if provider == "jimeng":
            if reference_image_url and settings.image_reference_fallback_direct:
                return reference_image_url
            return None

    if provider == "dashscope" or settings.dashscope_api_key:
        generated = _generate_dashscope_look(prompt)
        if generated:
            return generated
        if reference_image_url and settings.image_reference_fallback_direct:
            return reference_image_url
        return None

    if reference_image_url and settings.image_reference_fallback_direct:
        return reference_image_url
    return None
