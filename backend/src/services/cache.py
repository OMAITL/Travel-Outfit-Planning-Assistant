"""Local disk cache for external API responses."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from diskcache import Cache

from src.config import get_settings

_CACHE: Cache | None = None
DEFAULT_TTL = 86400  # 24 hours


def get_cache() -> Cache:
    global _CACHE
    if _CACHE is None:
        settings = get_settings()
        settings.cache_dir.mkdir(parents=True, exist_ok=True)
        _CACHE = Cache(str(settings.cache_dir))
    return _CACHE


def make_cache_key(namespace: str, **params: Any) -> str:
    payload = json.dumps(params, sort_keys=True, ensure_ascii=False, default=str)
    digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
    return f"{namespace}:{digest}"


def cache_get(namespace: str, **params: Any) -> Any | None:
    key = make_cache_key(namespace, **params)
    return get_cache().get(key)


def cache_set(namespace: str, value: Any, ttl: int = DEFAULT_TTL, **params: Any) -> None:
    key = make_cache_key(namespace, **params)
    get_cache().set(key, value, expire=ttl)
