"""Run all 6 agent nodes in sequence (manual E2E demo)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path

import httpx

import src.graph  # noqa: F401 — triggers PlanningState.model_rebuild()

from src.config import get_settings
from src.graph.nodes import (
    image_node,
    report_node,
    shopping_node,
    stylist_node,
    trip_node,
    weather_node,
)
from src.graph.state import (
    ChatMessage,
    DailyOutfit,
    PlanningPhase,
    PlanningState,
)

USER_MESSAGE = "7月10日到12日去大理，休闲风，拍照逛街，单件预算200元"
FIXTURE_PATH = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "planning_state.json"


def check_llm() -> str | None:
    """Return an error message if the LLM API is not reachable, else None."""
    settings = get_settings()
    if not settings.openai_api_key:
        return "OPENAI_API_KEY 未配置，请在 backend/.env 中填写。"

    base = settings.openai_api_base.rstrip("/")
    if not base.endswith("/v1"):
        base = f"{base}/v1"

    try:
        response = httpx.post(
            f"{base}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.openai_model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 5,
            },
            timeout=20.0,
        )
    except httpx.HTTPError as exc:
        return f"无法连接 LLM 服务 ({settings.openai_api_base}): {exc}"

    if response.status_code == 401:
        return (
            "LLM 认证失败 (401)：OPENAI_API_KEY 无效，或与 OPENAI_API_BASE 不匹配。\n"
            "  DeepSeek: https://platform.deepseek.com 创建 Key，并设置\n"
            "    OPENAI_API_BASE=https://api.deepseek.com/v1\n"
            "    OPENAI_MODEL=deepseek-chat"
        )
    if response.status_code >= 400:
        return f"LLM 请求失败 ({response.status_code}): {response.text[:300]}"
    return None


def mock_seed_state() -> PlanningState:
    """Seed state from fixture; skip Trip/Stylist LLM calls."""
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    state = PlanningState.model_validate(payload)
    trip = state.trip
    if trip is None:
        msg = "Fixture missing trip"
        raise ValueError(msg)

    outfits: list[DailyOutfit] = []
    day = trip.start_date
    template = state.outfits[0] if state.outfits else DailyOutfit(
        date=day,
        outfit_summary="轻薄防晒衬衫 + 亚麻阔腿裤 + 白色运动鞋",
        search_keywords=["女 防晒 衬衫 夏季", "女 亚麻 阔腿裤"],
    )
    while day <= trip.end_date:
        outfits.append(
            template.model_copy(
                update={
                    "date": day,
                    "outfit_summary": f"[{day}] {template.outfit_summary}",
                }
            )
        )
        day += timedelta(days=1)

    return state.model_copy(
        update={
            "phase": PlanningPhase.PLANNING,
            "weather": [],
            "outfits": outfits,
            "look_images": [],
            "products": [],
            "report": None,
            "errors": [],
            "trace": [],
        }
    )


def run_pipeline(state: PlanningState, *, use_llm: bool) -> PlanningState:
    if use_llm:
        print("=== Trip ===")
        state = trip_node(state)
        print("phase:", state.phase)
        if state.trip:
            print("destination:", state.trip.destination, "days:", state.trip.trip_days)
        if state.phase == PlanningPhase.COLLECTING:
            print("需要补全信息，助手回复:", state.messages[-1].content)
            return state
    else:
        print("=== Trip (mock, skipped LLM) ===")
        print("destination:", state.trip.destination if state.trip else "?")

    print("\n=== Weather ===")
    state = weather_node(state)
    print("weather days:", len(state.weather))

    if use_llm:
        print("\n=== Stylist (LLM, may take a while) ===")
        state = stylist_node(state)
    else:
        print("\n=== Stylist (mock, using fixture outfits) ===")
    print("outfits:", len(state.outfits))

    print("\n=== Image (Jimeng) ===")
    state = image_node(state)
    print("look_images:", len(state.look_images))

    print("\n=== Shopping (OneBound) ===")
    state = shopping_node(state)
    print("products:", len(state.products))

    print("\n=== Report ===")
    state = report_node(state)
    if not state.report:
        print("no report generated")
        return state

    print(state.report.summary)
    for card in state.report.daily_cards:
        outfit = card.outfit.outfit_summary if card.outfit else "-"
        print(f"\n{card.date}")
        print("  穿搭:", outfit)
        print("  图:", card.look_image_url or "无")
        print("  商品:", len(card.products))
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description="Run agent nodes demo")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Skip Trip/Stylist LLM; use fixture trip/outfits",
    )
    args = parser.parse_args()

    if args.mock:
        state = mock_seed_state()
        run_pipeline(state, use_llm=False)
        return

    llm_error = check_llm()
    if llm_error:
        print(llm_error, file=sys.stderr)
        print(
            "\n可先跳过 LLM 测试其余节点：\n  uv run python scripts/demo_nodes.py --mock",
            file=sys.stderr,
        )
        sys.exit(1)

    state = PlanningState(
        messages=[ChatMessage(role="user", content=USER_MESSAGE)],
    )
    run_pipeline(state, use_llm=True)


if __name__ == "__main__":
    main()
