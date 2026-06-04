"""
Test Just One API — 商品搜索 V1 + 小红书穿搭参考

默认 dry-run；加 --live 会消耗 API 次数。

用法:
  uv run python scripts/test_justone_search.py
  uv run python scripts/test_justone_search.py --live --keyword "女 防晒 衬衫"
  uv run python scripts/test_justone_xhs.py --live --keyword "大理 穿搭"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from src.config import reload_settings
from src.services.product_matcher import to_product_card
from src.tools.justone_client import JustOneApiError
from src.tools.justoneapi import search_taobao_items

CN_BASE_URL = "http://47.117.133.51:30015"


def main() -> int:
    parser = argparse.ArgumentParser(description="Test Just One API Taobao search v1")
    parser.add_argument("--live", action="store_true", help="Call API (consumes quota)")
    parser.add_argument("--keyword", default="女 防晒 衬衫")
    parser.add_argument("--max-price", type=float, default=200.0)
    parser.add_argument("--cn", action="store_true", help="Use mainland mirror")
    args = parser.parse_args()

    settings = reload_settings()
    token = settings.justoneapi_token or ""
    base = CN_BASE_URL if args.cn else settings.justoneapi_base_url

    print("=== Just One API · 商品搜索 V1 ===")
    print(f"BASE_URL: {base}")
    print(f"TOKEN:    {'已配置 (' + token[:4] + '…)' if len(token) >= 4 else '未配置'}")
    print(f"KEYWORD:  {args.keyword}")
    print(f"SORT:     {settings.justoneapi_sort}")
    print()

    if not token:
        print("ERROR: 请在 backend/.env 设置 JUSTONEAPI_TOKEN")
        return 1

    if not args.live:
        print("【dry-run】未发起请求。真实调用:")
        print(f'  uv run python scripts/test_justone_search.py --live --keyword "{args.keyword}"')
        return 0

    if args.cn:
        import os

        os.environ["JUSTONEAPI_BASE_URL"] = CN_BASE_URL
        reload_settings()

    print("【live】正在搜索…")
    try:
        items = search_taobao_items(args.keyword, max_price=args.max_price, use_cache=False)
    except JustOneApiError as exc:
        print("FAILED:", exc)
        if exc.error_code == "601":
            print("提示: 余额不足，搜索接口无法扣费；商品详情若可用说明部分接口仍有余额。")
        return 1
    except ValueError as exc:
        print("CONFIG:", exc)
        return 1

    print(f"OK: {len(items)} item(s)")
    for index, item in enumerate(items[:3], start=1):
        card = to_product_card(item, max_price=args.max_price)
        print(f"\n[{index}] {item.get('title', '')[:60]}")
        print("  price:", item.get("price"))
        print("  pic:", (item.get("pic_url") or "")[:80])
        print("  link:", (item.get("detail_url") or "")[:80])
        print("  card:", "OK" if card else "parse failed")

    if not items:
        print("\n搜索成功但 itemList 为空 — 可能是套餐权限或余额只够详情不够搜索。")
        print("可尝试: uv run python scripts/test_justone_item_detail.py --live --item-id <id>")

    return 0 if items else 1


if __name__ == "__main__":
    raise SystemExit(main())
