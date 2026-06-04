"""
Test Just One API — 商品详情 V1（连通性探测）

默认 dry-run：不发起 HTTP，不消耗额度，只检查配置与请求 URL。
真实调用会消耗 Just One API 次数，需显式加 --live。

文档: https://docs.justoneapi.com/zh/api/taobao-and-tmall/product-details-v1

用法:
  uv run python scripts/test_justone_item_detail.py
  uv run python scripts/test_justone_item_detail.py --live --item-id 620210933491
  uv run python scripts/test_justone_item_detail.py --live --cn --item-id 620210933491
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from src.config import reload_settings

DETAIL_PATH = "/api/taobao/get-item-detail/v1"
REQUEST_TIMEOUT = httpx.Timeout(connect=15.0, read=90.0, write=15.0, pool=15.0)

SUCCESS_CODES = {"0", "200"}
CN_BASE_URL = "http://47.117.133.51:30015"
RETRYABLE_CODES = {"301", "302"}

ERROR_HINTS: dict[str, str] = {
    "100": "Token 无效或已失效",
    "301": "采集失败，请重试（可 --cn 换国内节点）",
    "302": "超出速率限制，请降低调用频率",
    "303": "超出每日配额",
    "400": "参数错误，请检查 itemId",
    "500": "Just One 内部服务器错误",
    "600": "权限不足，请检查套餐是否含商品详情",
    "601": "余额不足，请充值",
}


def build_detail_url(*, base_url: str, token: str, item_id: str) -> str:
    base = base_url.rstrip("/")
    params = urlencode({"token": token, "itemId": item_id})
    return f"{base}{DETAIL_PATH}?{params}"


def fetch_item_detail(*, base_url: str, token: str, item_id: str) -> dict[str, Any]:
    url = build_detail_url(base_url=base_url, token=token, item_id=item_id)
    response = httpx.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        msg = f"Unexpected response type: {type(payload).__name__}"
        raise ValueError(msg)
    return payload


def _first_str(data: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def summarize_item_detail(data: object) -> dict[str, str]:
    """Extract common fields from varying Just One detail payloads."""
    if not isinstance(data, dict):
        return {}

    # Some responses nest item under data.item / data.itemInfo / data.model
    block: dict[str, Any] = data
    for key in ("item", "itemInfo", "model", "itemDetail"):
        nested = data.get(key)
        if isinstance(nested, dict):
            block = nested
            break

    title = _first_str(block, "title", "itemTitle", "name")
    price = _first_str(
        block,
        "promotion_price",
        "promotionPrice",
        "price",
        "zkFinalPrice",
        "couponPrice",
        "viewPrice",
    )
    pic = _first_str(block, "pic_url", "pic", "mainImageUrl", "mainPic", "image", "img")
    shop = _first_str(block, "shopName", "nick", "sellerNick", "shopTitle")
    num_iid = _first_str(block, "num_iid", "itemId", "item_id", "id")
    detail_url = _first_str(block, "detail_url", "detailUrl", "itemUrl", "url")

    return {
        k: v
        for k, v in {
            "itemId": num_iid,
            "title": title,
            "price": price,
            "pic_url": pic,
            "shop": shop,
            "detail_url": detail_url,
        }.items()
        if v
    }


def print_error(code: str, message: str) -> None:
    print(f"code: {code}")
    print(f"message: {message}")
    hint = ERROR_HINTS.get(code)
    if hint:
        print(f"提示: {hint}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Test Just One API item detail v1")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Actually call the API (consumes quota). Default is dry-run only.",
    )
    parser.add_argument(
        "--item-id",
        default="620210933491",
        help="Taobao item ID (default: 620210933491)",
    )
    parser.add_argument(
        "--cn",
        action="store_true",
        help="Use mainland mirror (http://47.117.133.51:30015)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="Retry count when code=301/302 (default 2)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full JSON response on success (may be long)",
    )
    args = parser.parse_args()

    settings = reload_settings()
    token = settings.justoneapi_token or ""
    base = CN_BASE_URL if args.cn else settings.justoneapi_base_url

    print("=== Just One API · 商品详情 V1 ===")
    print(f"BASE_URL: {base}")
    print(f"TOKEN:    {'已配置 (' + token[:4] + '…)' if len(token) >= 4 else '未配置'}")
    print(f"ITEM_ID:  {args.item_id}")
    print()

    if not token:
        print("ERROR: 请在 backend/.env 设置 JUSTONEAPI_TOKEN")
        return 1

    if not args.item_id.strip():
        print("ERROR: itemId 不能为空")
        return 1

    safe_url = build_detail_url(base_url=base, token="***", item_id=args.item_id)
    print("请求路径（脱敏）:")
    print(safe_url)
    print()

    if not args.live:
        print("【dry-run 模式】未发起网络请求，不消耗 API 次数。")
        print()
        print("若确认要真实调用（会扣次数），运行:")
        print(
            f"  uv run python scripts/test_justone_item_detail.py --live --item-id {args.item_id}"
        )
        print("中国大陆用户可追加 --cn 使用国内节点。")
        return 0

    print("【live 模式】正在调用 API（将消耗次数）…")
    payload: dict[str, Any] | None = None
    try:
        for attempt in range(args.retries + 1):
            if attempt > 0:
                wait = 3 * attempt
                print(f"  重试 {attempt}/{args.retries}，等待 {wait}s …")
                time.sleep(wait)
            payload = fetch_item_detail(
                base_url=base,
                token=token,
                item_id=args.item_id.strip(),
            )
            code = str(payload.get("code", ""))
            if code in SUCCESS_CODES:
                break
            if code not in RETRYABLE_CODES:
                break
    except httpx.HTTPError as exc:
        print(f"HTTP 失败: {exc}")
        if not args.cn:
            print("可尝试国内节点: --cn")
        return 1
    except ValueError as exc:
        print(f"响应解析失败: {exc}")
        return 1

    assert payload is not None
    code = str(payload.get("code", ""))
    message = str(payload.get("message") or payload.get("msg") or "")

    if code not in SUCCESS_CODES:
        print_error(code, message)
        return 1

    print(f"code: {code}")
    if message:
        print(f"message: {message}")

    data = payload.get("data")
    summary = summarize_item_detail(data)
    if summary:
        print()
        print("商品摘要:")
        for key, value in summary.items():
            display = value if len(value) <= 120 else value[:117] + "…"
            print(f"  {key}: {display}")
    else:
        preview = json.dumps(data, ensure_ascii=False)[:800]
        print("data 预览:", preview if preview else "(empty)")

    if args.json:
        print()
        print(json.dumps(payload, ensure_ascii=False, indent=2))

    print()
    print("OK — 商品详情接口调用成功。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
