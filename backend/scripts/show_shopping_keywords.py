"""Print Taobao search keywords from a PlanningState JSON file or stdin."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import src.graph  # noqa: F401
from src.graph.state import PlanningState


def _load_state(path: Path | None) -> PlanningState:
    if path is None:
        payload = json.load(sys.stdin)
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
    return PlanningState.model_validate(payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show Taobao search keywords from planning trace")
    parser.add_argument(
        "state_json",
        nargs="?",
        help="PlanningState JSON file (default: stdin)",
    )
    args = parser.parse_args(argv)

    state = _load_state(Path(args.state_json) if args.state_json else None)
    shopping = [event for event in state.trace if event.agent == "Shopping"]

    if not shopping:
        print("No Shopping trace entries found.", file=sys.stderr)
        return 1

    print("=== Shopping trace ===")
    api_calls = 0
    for event in shopping:
        print(f"[{event.level}] {event.message}")
        if event.message.startswith("Taobao API:"):
            api_calls += 1

    print(f"\nTotal Taobao API calls logged: {api_calls}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
