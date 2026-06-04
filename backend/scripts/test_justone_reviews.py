"""
Test Just One API — 商品评价 V3（连通性探测）

默认 --dry-run：不发起 HTTP，不消耗额度，只检查配置与请求 URL。

真实调用会消耗 Just One API 次数，需显式加 --live。

文档: https://docs.justoneapi.com/zh/api/taobao-and-tmall/product-reviews-v3

用法:
  uv run python scripts/test_justone_reviews.py
  uv run python scripts/test_justone_reviews.py --live --item-id 123456789
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from src.config import reload_settings

REVIEWS_PATH = "/api/taobao/get-item-comment/v3"
REQUEST_TIMEOUT = httpx.Timeout(connect=15.0, read=90.0, write=15.0, pool=15.0)

SUCCESS_CODES = {"0", "200"}
CN_BASE_URL = "http://47.117.133.51:30015"
RETRYABLE_CODES = {"301", "302"}


def build_reviews_url(
    *,
    base_url: str,
    token: str,
    item_id: str,
    page: int = 1,
    order_type: str = "feedbackdate",
) -> str:
    base = base_url.rstrip("/")
    params = urlencode(
        {
            "token": token,
            "itemId": item_id,
            "page": page,
            "orderType": order_type,
        }
    )
    return f"{base}{REVIEWS_PATH}?{params}"


def fetch_reviews(
    *,
    base_url: str,
    token: str,
    item_id: str,
    page: int = 1,
) -> dict:
    url = build_reviews_url(
        base_url=base_url,
        token=token,
        item_id=item_id,
        page=page,
    )
    response = httpx.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def main() -> int:
    parser = argparse.ArgumentParser(description="Test Just One API item reviews v3")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Actually call the API (consumes quota). Default is dry-run only.",
    )
    parser.add_argument(
        "--item-id",
        default="123456789",
        help="Taobao item ID for --live test (default: placeholder)",
    )
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument(
        "--cn",
        action="store_true",
        help="Use mainland mirror (47.117.133.51:30015)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="Retry count when code=301/302 (default 2)",
    )
    args = parser.parse_args()

    settings = reload_settings()
    token = settings.justoneapi_token or ""
    base = CN_BASE_URL if args.cn else settings.justoneapi_base_url

    print("=== Just One API · 商品评价 V3 ===")
    print(f"BASE_URL: {base}")
    print(f"TOKEN:    {'已配置 (' + token[:4] + '…)' if len(token) >= 4 else '未配置'}")
    print(f"ITEM_ID:  {args.item_id}")
    print()

    if not token:
        print("ERROR: 请在 backend/.env 设置 JUSTONEAPI_TOKEN")
        return 1

    safe_url = build_reviews_url(
        base_url=base,
        token="***",
        item_id=args.item_id,
        page=args.page,
    )
    print("请求路径（脱敏）:")
    print(safe_url)
    print()

    if not args.live:
        print("【dry-run 模式】未发起网络请求，不消耗 API 次数。")
        print()
        print("若确认要真实调用（会扣次数），运行:")
        print(f"  uv run python scripts/test_justone_reviews.py --live --item-id {args.item_id}")
        print()
        print("说明:")
        print("  · 本脚本测的是「商品评价」接口，仅验证 Token/网络是否通。")
        print("  · 本项目购物搜索用的是「商品搜索 V1」:")
        print("    /api/taobao/search-item-list/v1")
        print("  · 文档页「测试接口」按钮通常也会扣次数，以控制台余额为准。")
        print("  · 零消耗验证代码逻辑: uv run pytest tests/test_justoneapi.py -q")
        return 0

    print("【live 模式】正在调用 API（将消耗次数）…")
    payload: dict | None = None
    last_code = ""
    try:
        for attempt in range(args.retries + 1):
            if attempt > 0:
                wait = 3 * attempt
                print(f"  重试 {attempt}/{args.retries}，等待 {wait}s …")
                time.sleep(wait)
            payload = fetch_reviews(
                base_url=base,
                token=token,
                item_id=args.item_id,
                page=args.page,
            )
            last_code = str(payload.get("code", ""))
            if last_code in SUCCESS_CODES:
                break
            if last_code not in RETRYABLE_CODES:
                break
    except httpx.HTTPError as exc:
        print(f"HTTP 失败: {exc}")
        if not args.cn:
            print("可尝试国内节点: --cn")
        return 1

    assert payload is not None
    code = str(payload.get("code", ""))
    message = payload.get("message", "")
    print(f"code: {code}")
    print(f"message: {message}")

    if code not in SUCCESS_CODES:
        hints = {
            "100": "Token 无效或已失效",
            "301": "采集失败（临时），文档建议重试；可 --cn 换国内节点，或改测搜索接口",
            "302": "速率限制，稍后重试",
            "303": "每日配额用尽",
            "601": "余额不足",
        }
        if code in hints:
            print(f"提示: {hints[code]}")
        if code == "301":
            print()
            print("301 ≠ Token 错误。说明请求已到达 Just One，但抓取淘宝评价失败。")
            print("建议下一步（项目实际用的是搜索，不是评价）:")
            print("  uv run python scripts/test_justoneapi.py")
            print("或评价重试:")
            print(f"  uv run python scripts/test_justone_reviews.py --live --cn --item-id {args.item_id}")
        return 1

    data = payload.get("data")
    preview = json.dumps(data, ensure_ascii=False)[:800]
    print("data 预览:", preview if preview else "(empty)")
    print()
    print("OK — Token 有效，评价接口可用。")
    print("购物搜索请再测: uv run python scripts/test_justoneapi.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
