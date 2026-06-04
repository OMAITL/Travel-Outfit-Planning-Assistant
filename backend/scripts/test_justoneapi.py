"""Quick Just One API connectivity check — run: uv run python scripts/test_justoneapi.py"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from src.config import reload_settings
from src.services.product_matcher import to_product_card
from src.tools.justoneapi import JustOneApiError, search_taobao_items


def main() -> int:
    settings = reload_settings()
    token = settings.justoneapi_token or ""
    print("JUSTONEAPI_TOKEN:", (token[:8] + "…") if len(token) > 8 else ("missing" if not token else token))
    print("BASE_URL:", settings.justoneapi_base_url)
    keyword = "女 防晒 衬衫"
    print(f"Searching: {keyword!r} (max_price=200)")

    try:
        items = search_taobao_items(keyword, max_price=200, use_cache=False)
    except JustOneApiError as exc:
        print("FAILED:", exc)
        if exc.error_code in {"303", "601"}:
            print("\n→ 配额或余额不足，请在 Just One API 控制台充值")
        return 1
    except ValueError as exc:
        print("CONFIG ERROR:", exc)
        return 1

    print(f"OK: {len(items)} item(s)")
    if items:
        card = to_product_card(items[0], max_price=200)
        print("Sample title:", items[0].get("title", "")[:50])
        print("Sample pic_url:", (items[0].get("pic_url") or "")[:70])
        print("Sample detail_url:", (items[0].get("detail_url") or "")[:70])
        print("ProductCard:", "OK" if card else "parse failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
