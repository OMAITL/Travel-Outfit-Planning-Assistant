"""Manual Taobao scraper test — run from backend/: uv run python scripts/test_scraper.py [keyword] [--debug]"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import httpx  # noqa: E402

from src.tools.taobao_scraper import (  # noqa: E402
    DEFAULT_USER_AGENT,
    TAOBAO_SEARCH_URL,
    TaobaoScraperError,
    build_taobao_search_url,
    diagnose_scrape_response,
    search_taobao_items_scrape,
)


def _fetch_html(keyword: str) -> tuple[str, str]:
    response = httpx.get(
        TAOBAO_SEARCH_URL,
        params={"q": keyword},
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Referer": "https://www.taobao.com/",
        },
        timeout=20.0,
        follow_redirects=True,
    )
    response.raise_for_status()
    return response.text, str(response.url)


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--debug"]
    debug = "--debug" in sys.argv
    keyword = args[0] if args else "女 防晒 衬衫"

    print(f"Keyword: {keyword}")
    print(f"Fallback URL: {build_taobao_search_url(keyword)}")
    print("Attempting scrape (may be blocked by Taobao)…\n")

    if debug:
        html, url = _fetch_html(keyword)
        diag = diagnose_scrape_response(html, final_url=url)
        print("Diagnostics:")
        for key, value in diag.items():
            print(f"  {key}: {value}")
        cache_dir = BACKEND_ROOT / ".cache"
        cache_dir.mkdir(exist_ok=True)
        dump_path = cache_dir / "scrape_debug.html"
        dump_path.write_text(html, encoding="utf-8", errors="replace")
        print(f"\nSaved HTML → {dump_path}")
        if diag.get("spa_shell"):
            print(
                "\n→ 结论：页面是 JS 空壳（商品由浏览器动态加载），"
                "纯 httpx 爬虫无法拿到列表。请在 .env 设置 PRODUCT_SOURCE=mock"
            )
        print()

    try:
        items = search_taobao_items_scrape(keyword, max_price=300, use_cache=False)
    except TaobaoScraperError as exc:
        print(f"FAILED: {exc}")
        if exc.blocked:
            print("\n→ 建议使用 PRODUCT_SOURCE=mock（见 backend/.env.example）")
        sys.exit(1)

    for idx, item in enumerate(items[:5], start=1):
        print(f"{idx}. {item.get('title')}")
        print(f"   ¥{item.get('price')}  {item.get('detail_url')}")
        print(f"   img: {str(item.get('pic_url', ''))[:60]}…")
    print(f"\nOK — {len(items)} item(s) parsed")


if __name__ == "__main__":
    main()
