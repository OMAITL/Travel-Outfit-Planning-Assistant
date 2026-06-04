"""Just One API — Xiaohongshu note search + detail for outfit inspiration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.tools.justone_client import JustOneApiError, justone_get

XHS_SEARCH_PATH = "/api/xiaohongshu/search-note/v2"
XHS_DETAIL_PATH = "/api/xiaohongshu/get-note-detail/v2"
XHS_NOTE_URL = "https://www.xiaohongshu.com/explore/{note_id}"


@dataclass
class XhsNoteSummary:
    note_id: str
    title: str
    cover_url: str
    image_urls: list[str] = field(default_factory=list)
    note_url: str = ""
    liked_count: int | None = None
    user_name: str | None = None

    def __post_init__(self) -> None:
        if not self.note_url:
            self.note_url = XHS_NOTE_URL.format(note_id=self.note_id)


def _first_str(data: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _normalize_image_url(raw: object) -> str:
    if isinstance(raw, str):
        url = raw.strip()
    elif isinstance(raw, dict):
        url = str(raw.get("url") or raw.get("urlDefault") or raw.get("original") or "").strip()
    else:
        return ""
    if url.startswith("//"):
        return f"https:{url}"
    return url


def _extract_image_urls(block: object) -> list[str]:
    urls: list[str] = []
    if isinstance(block, list):
        for entry in block:
            url = _normalize_image_url(entry)
            if url and url not in urls:
                urls.append(url)
    elif isinstance(block, dict):
        for key in ("images_list", "image_list", "images", "imageList", "cover"):
            nested = block.get(key)
            if nested is not None:
                urls.extend(_extract_image_urls(nested))
    return urls


def _unwrap_note(raw: dict[str, Any]) -> dict[str, Any]:
    note = raw.get("note")
    if isinstance(note, dict):
        return note
    return raw


def _map_note_summary(raw: dict[str, Any]) -> XhsNoteSummary | None:
    note = _unwrap_note(raw)
    note_id = _first_str(note, "id", "note_id", "noteId")
    if not note_id:
        return None

    title = _first_str(note, "display_title", "title", "desc")
    image_urls = _extract_image_urls(note)
    cover_url = image_urls[0] if image_urls else ""

    user = note.get("user")
    user_name = None
    if isinstance(user, dict):
        user_name = _first_str(user, "nickname", "name", "nick")

    liked_raw = note.get("liked_count") or note.get("likes")
    liked_count = int(liked_raw) if liked_raw is not None and str(liked_raw).isdigit() else None

    note_type = str(note.get("type") or "").lower()
    if note_type == "video" and not image_urls:
        return None

    return XhsNoteSummary(
        note_id=note_id,
        title=title,
        cover_url=cover_url,
        image_urls=image_urls,
        liked_count=liked_count,
        user_name=user_name,
    )


def search_xhs_notes(
    keyword: str,
    *,
    page: int = 1,
    sort: str = "general",
    note_type: str = "_2",
    use_cache: bool = True,
) -> list[XhsNoteSummary]:
    """Search Xiaohongshu notes via Just One API search-note v2."""
    keyword = keyword.strip()
    if not keyword:
        return []

    cache_params = {
        "keyword": keyword,
        "page": page,
        "sort": sort,
        "note_type": note_type,
    }
    payload = justone_get(
        XHS_SEARCH_PATH,
        {
            "keyword": keyword,
            "page": page,
            "sort": sort,
            "noteType": note_type,
        },
        use_cache=use_cache,
        cache_namespace="justoneapi_xhs_search",
        cache_params=cache_params,
    )

    data = payload.get("data")
    if not isinstance(data, dict):
        return []

    items = data.get("items") or []
    summaries: list[XhsNoteSummary] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        summary = _map_note_summary(item)
        if summary is not None:
            summaries.append(summary)
    return summaries


def get_xhs_note_detail(
    note_id: str,
    *,
    use_cache: bool = True,
) -> XhsNoteSummary | None:
    """Fetch Xiaohongshu note detail via get-note-detail v2."""
    note_id = note_id.strip()
    if not note_id:
        return None

    cache_params = {"note_id": note_id}
    payload = justone_get(
        XHS_DETAIL_PATH,
        {"noteId": note_id},
        use_cache=use_cache,
        cache_namespace="justoneapi_xhs_detail",
        cache_params=cache_params,
    )

    data = payload.get("data")
    if isinstance(data, dict):
        summary = _map_note_summary(data)
        if summary is not None:
            return summary
    return None


def fetch_outfit_inspirations(
    keyword: str,
    *,
    max_notes: int = 2,
    fetch_detail: bool = True,
    max_api_calls: int | None = None,
) -> tuple[list[XhsNoteSummary], int]:
    """
    Search XHS notes and optionally enrich with note detail for full image lists.

    Returns (notes, api_calls_used).
    """
    if max_notes <= 0:
        return [], 0

    calls = 1
    if max_api_calls is not None and calls > max_api_calls:
        return [], 0

    try:
        candidates = search_xhs_notes(keyword, note_type="_2")
    except JustOneApiError:
        raise

    picked: list[XhsNoteSummary] = []
    for candidate in candidates:
        if len(picked) >= max_notes:
            break
        if not candidate.cover_url and not candidate.image_urls:
            continue

        note = candidate
        if fetch_detail and (max_api_calls is None or calls < max_api_calls):
            try:
                detailed = get_xhs_note_detail(candidate.note_id)
                calls += 1
                if detailed is not None:
                    merged_urls = list(detailed.image_urls)
                    for url in candidate.image_urls:
                        if url not in merged_urls:
                            merged_urls.append(url)
                    note = XhsNoteSummary(
                        note_id=detailed.note_id,
                        title=detailed.title or candidate.title,
                        cover_url=detailed.cover_url or candidate.cover_url,
                        image_urls=merged_urls or candidate.image_urls,
                        liked_count=detailed.liked_count or candidate.liked_count,
                        user_name=detailed.user_name or candidate.user_name,
                    )
            except JustOneApiError:
                note = candidate

        if note.cover_url or note.image_urls:
            picked.append(note)

    return picked, calls
