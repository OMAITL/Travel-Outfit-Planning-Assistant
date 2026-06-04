"""
Test Just One API — 小红书笔记搜索 V2 + 笔记详情 V2

流程: 关键词搜索 → 取 noteId → 拉详情拿完整图片列表（与线上一致）。

用法:
  uv run python scripts/test_justone_xhs.py
  uv run python scripts/test_justone_xhs.py --live --keyword "大理 穿搭"
  uv run python scripts/test_justone_xhs.py --live --cn --no-detail
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from src.config import reload_settings
from src.tools.justone_client import JustOneApiError
from src.tools.justone_xhs import fetch_outfit_inspirations, search_xhs_notes

CN_BASE_URL = "http://47.117.133.51:30015"


def main() -> int:
    parser = argparse.ArgumentParser(description="Test Just One XHS search + detail")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--keyword", default="大理 穿搭")
    parser.add_argument("--max-notes", type=int, default=2)
    parser.add_argument("--cn", action="store_true")
    parser.add_argument(
        "--no-detail",
        action="store_true",
        help="Only use search results (1 API call), skip note detail",
    )
    args = parser.parse_args()

    settings = reload_settings()
    token = settings.justoneapi_token or ""
    base = CN_BASE_URL if args.cn else settings.justoneapi_base_url

    print("=== Just One API · 小红书穿搭参考 ===")
    print(f"BASE_URL: {base}")
    print(f"TOKEN:    {'已配置 (' + token[:4] + '…)' if len(token) >= 4 else '未配置'}")
    print(f"KEYWORD:  {args.keyword}")
    print(f"流程:     搜索 V2 → {'仅封面' if args.no_detail else '详情 V2 补全图片'}")
    print()

    if not token:
        print("ERROR: 请在 backend/.env 设置 JUSTONEAPI_TOKEN")
        return 1

    if not args.live:
        print("【dry-run】未发起请求。真实调用:")
        print(f'  uv run python scripts/test_justone_xhs.py --live --keyword "{args.keyword}"')
        return 0

    if args.cn:
        import os

        os.environ["JUSTONEAPI_BASE_URL"] = CN_BASE_URL
        reload_settings()

    print("【live】正在调用…")
    try:
        if args.no_detail:
            notes = search_xhs_notes(args.keyword, use_cache=False)
            used = 1
        else:
            notes, used = fetch_outfit_inspirations(
                args.keyword,
                max_notes=args.max_notes,
                fetch_detail=True,
            )
    except JustOneApiError as exc:
        print("FAILED:", exc)
        return 1

    print(f"API 调用次数: {used}")
    print(f"笔记数: {len(notes)}")
    for index, note in enumerate(notes, start=1):
        print(f"\n[{index}] {note.title[:60] if note.title else note.note_id}")
        print("  note_id:", note.note_id)
        print("  note_url:", note.note_url)
        print("  cover:", (note.cover_url or "")[:90])
        print("  images:", len(note.image_urls))
        if note.user_name:
            print("  user:", note.user_name)
        if note.liked_count is not None:
            print("  likes:", note.liked_count)

    if notes:
        print("\nOK — 搜索→详情链路可用。")
        return 0

    print("\n未找到带图笔记，可换关键词重试。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
