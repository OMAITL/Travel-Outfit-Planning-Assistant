"""Quick OneBound connectivity check — run from backend/: uv run python scripts/test_onebound.py"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from src.config import reload_settings
from src.services.product_matcher import to_product_card
from src.tools.onebound import OneBoundError, search_taobao_items


def main() -> int:
    settings = reload_settings()
    print("ONEBOUND_KEY:", (settings.onebound_key or "")[:6] + "…" if settings.onebound_key else "missing")
    keyword = "女 防晒 衬衫"
    print(f"Searching: {keyword!r}")

    try:
        items = search_taobao_items(keyword, max_price=200, use_cache=False)
    except OneBoundError as exc:
        print("FAILED:", exc)
        if exc.error_code == "4013":
            print("\n→ 调用次数已超限，请登录 https://open.onebound.cn 充值或升级套餐")
        return 1
    except ValueError as exc:
        print("CONFIG ERROR:", exc)
        return 1

    print(f"OK: {len(items)} item(s)")
    if items:
        card = to_product_card(items[0])
        print("Sample title:", items[0].get("title", "")[:40])
        print("Sample pic_url:", items[0].get("pic_url", "")[:60])
        print("Sample detail_url:", items[0].get("detail_url", "")[:60])
        print("ProductCard:", "OK" if card else "parse failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
