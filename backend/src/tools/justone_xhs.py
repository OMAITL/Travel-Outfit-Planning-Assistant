"""Just One API — Xiaohongshu note search (v3) + detail (v2) for outfit inspiration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

from src.tools.justone_client import JustOneApiError, justone_get

XHS_SEARCH_PATH = "/api/xiaohongshu/search-note/v3"
XHS_DETAIL_PATH = "/api/xiaohongshu/get-note-detail/v2"
XHS_NOTE_URL = "https://www.xiaohongshu.com/explore/{note_id}"


@dataclass
class XhsNoteSummary:
    note_id: str
    title: str
    cover_url: str
    image_urls: list[str] = field(default_factory=list)
    note_url: str = ""
    desc: str = ""
    liked_count: int | None = None
    user_name: str | None = None
    note_type: str | None = None

    def __post_init__(self) -> None:
        if not self.note_url:
            self.note_url = XHS_NOTE_URL.format(note_id=self.note_id)


def _first_str(data: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _parse_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_image_url(raw: object) -> str:
    if isinstance(raw, str):
        url = raw.strip()
    elif isinstance(raw, dict):
        url = str(
            raw.get("original")
            or raw.get("url_size_large")
            or raw.get("url")
            or raw.get("urlDefault")
            or ""
        ).strip()
    else:
        return ""
    if not url:
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
        video_info = block.get("video_info_v2")
        if isinstance(video_info, dict):
            image_block = video_info.get("image")
            if isinstance(image_block, dict):
                for key in ("first_frame", "thumbnail", "thumbnail_dim"):
                    url = _normalize_image_url(image_block.get(key))
                    if url and url not in urls:
                        urls.append(url)
        for key in ("share_info", "mini_program_info", "qq_mini_program_info"):
            nested = block.get(key)
            if isinstance(nested, dict):
                for image_key in ("image", "thumb"):
                    url = _normalize_image_url(nested.get(image_key))
                    if url and url not in urls:
                        urls.append(url)
    return urls


def _unwrap_search_item(raw: dict[str, Any], *, include_ads: bool) -> dict[str, Any] | None:
    """Extract a note dict from search v3 result items (note / ads / hot_query)."""
    model_type = str(raw.get("model_type") or "").lower()
    if model_type == "hot_query":
        return None
    if model_type == "ads":
        if not include_ads:
            return None
        ads = raw.get("ads")
        if isinstance(ads, dict) and isinstance(ads.get("note"), dict):
            return ads["note"]
        return None

    note = raw.get("note")
    if isinstance(note, dict):
        return note
    return raw


def _build_note_url(note: dict[str, Any], note_id: str) -> str:
    share_info = note.get("share_info")
    if isinstance(share_info, dict):
        link = _first_str(share_info, "link")
        if link.startswith("http"):
            return link

    for key in ("mini_program_info", "qq_mini_program_info"):
        mini = note.get(key)
        if isinstance(mini, dict):
            webpage = _first_str(mini, "webpage_url")
            if webpage.startswith("http"):
                return webpage

    xsec_token = _first_str(note, "xsec_token")
    base = XHS_NOTE_URL.format(note_id=note_id)
    if not xsec_token:
        return base
    return f"{base}?{urlencode({'xsec_token': xsec_token})}"


def _unwrap_detail_note(data: object) -> dict[str, Any] | None:
    """Extract note dict from get-note-detail v2 payload (`data` array + `note_list`)."""
    if isinstance(data, dict):
        if _first_str(data, "id", "note_id", "noteId"):
            return data
        note_list = data.get("note_list")
        if isinstance(note_list, list):
            for entry in note_list:
                if isinstance(entry, dict) and _first_str(entry, "id", "note_id", "noteId"):
                    return entry
        note = data.get("note")
        if isinstance(note, dict):
            return note
        return None

    if isinstance(data, list):
        for entry in data:
            if not isinstance(entry, dict):
                continue
            note_list = entry.get("note_list")
            if isinstance(note_list, list):
                for note in note_list:
                    if isinstance(note, dict) and _first_str(note, "id", "note_id", "noteId"):
                        return note
            if _first_str(entry, "id", "note_id", "noteId"):
                return entry
    return None


def _map_note_summary(raw: dict[str, Any], *, note_url: str | None = None) -> XhsNoteSummary | None:
    note_id = _first_str(raw, "id", "note_id", "noteId")
    if not note_id:
        return None

    desc = _first_str(raw, "desc", "description")
    title = _first_str(raw, "title", "display_title")
    if not title:
        title = desc[:80] + ("…" if len(desc) > 80 else "") if desc else ""

    image_urls = _extract_image_urls(raw)
    cover_url = image_urls[0] if image_urls else ""

    user = raw.get("user")
    user_name = None
    if isinstance(user, dict):
        user_name = _first_str(user, "nickname", "name", "nick")

    note_type = _first_str(raw, "type") or None
    liked_count = _parse_int(raw.get("liked_count") or raw.get("likes"))

    if not cover_url and not image_urls:
        return None

    return XhsNoteSummary(
        note_id=note_id,
        title=title,
        cover_url=cover_url,
        image_urls=image_urls,
        note_url=note_url or _build_note_url(raw, note_id),
        desc=desc,
        liked_count=liked_count,
        user_name=user_name,
        note_type=note_type,
    )


def search_xhs_notes(
    keyword: str,
    *,
    page: int = 1,
    sort: str = "general",
    note_type: str = "_2",
    include_ads: bool = False,
    use_cache: bool = True,
) -> list[XhsNoteSummary]:
    """Search Xiaohongshu notes via Just One API search-note v3."""
    keyword = keyword.strip()
    if not keyword:
        return []

    cache_params = {
        "keyword": keyword,
        "page": page,
        "sort": sort,
        "note_type": note_type,
        "include_ads": include_ads,
        "api_version": "v3",
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
        cache_namespace="justoneapi_xhs_search_v3",
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
        note_block = _unwrap_search_item(item, include_ads=include_ads)
        if note_block is None:
            continue
        summary = _map_note_summary(note_block)
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

    note = _unwrap_detail_note(payload.get("data"))
    if note is None:
        return None
    return _map_note_summary(note)


def fetch_outfit_inspirations(
    keyword: str,
    *,
    max_notes: int = 2,
    fetch_detail: bool = True,
    max_api_calls: int | None = None,
    note_type: str = "_2",
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
        candidates = search_xhs_notes(keyword, note_type=note_type, include_ads=False)
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
                        note_url=detailed.note_url or candidate.note_url,
                        desc=detailed.desc or candidate.desc,
                        liked_count=detailed.liked_count or candidate.liked_count,
                        user_name=detailed.user_name or candidate.user_name,
                        note_type=detailed.note_type or candidate.note_type,
                    )
            except JustOneApiError:
                note = candidate

        if note.cover_url or note.image_urls:
            picked.append(note)

    return picked, calls
