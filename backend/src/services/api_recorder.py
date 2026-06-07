"""Persist external API request/response pairs for debugging and mock replay."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from src.config import BACKEND_ROOT, get_settings

Provider = Literal[
    "taobao_onebound",
    "taobao_justone",
    "xhs_justone",
    "jimeng",
    "deepseek",
]

_REDACT_KEY_PATTERN = re.compile(
    r"(token|secret|api[_-]?key|authorization|password|access[_-]?key)",
    re.IGNORECASE,
)
_OMIT_VALUE_KEYS = frozenset(
    {
        "binary_data_base64",
        "image_base64",
        "reference_image_base64",
    }
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _recordings_root() -> Path:
    settings = get_settings()
    root = settings.api_record_dir
    if not root.is_absolute():
        root = BACKEND_ROOT / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def _sanitize_value(key: str, value: Any) -> Any:
    if _REDACT_KEY_PATTERN.search(key):
        if value is None:
            return None
        text = str(value)
        if len(text) <= 8:
            return "***"
        return f"***{text[-4:]}"

    if key in _OMIT_VALUE_KEYS:
        if isinstance(value, list):
            return [
                {
                    "_omitted": True,
                    "type": "base64",
                    "length": len(str(item)),
                }
                for item in value
            ]
        if isinstance(value, str):
            return {"_omitted": True, "type": "base64", "length": len(value)}
        return {"_omitted": True, "type": type(value).__name__}

    if isinstance(value, dict):
        return {k: _sanitize_value(k, v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(key, item) for item in value]
    return value


def sanitize_payload(payload: Any) -> Any:
    """Remove secrets and bulky binary fields before writing to disk."""
    if isinstance(payload, dict):
        return {k: _sanitize_value(k, v) for k, v in payload.items()}
    if isinstance(payload, list):
        return [sanitize_payload(item) for item in payload]
    return payload


def request_hash(provider: str, operation: str, request: Any) -> str:
    """Stable hash for matching a later mock replay to a recorded exchange."""
    payload = json.dumps(
        {"provider": provider, "operation": operation, "request": sanitize_payload(request)},
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def record_api_exchange(
    provider: Provider,
    operation: str,
    request: Any,
    response: Any = None,
    *,
    status: Literal["success", "error"] = "success",
    error: str | None = None,
    duration_ms: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> str | None:
    """
    Write one request/response pair to disk. Returns record id, or None if disabled.
    """
    settings = get_settings()
    if not settings.api_record_enabled:
        return None

    record_id = uuid.uuid4().hex
    now = _utc_now()
    safe_request = sanitize_payload(request)
    safe_response = sanitize_payload(response)
    record = {
        "id": record_id,
        "timestamp": now.isoformat(),
        "provider": provider,
        "operation": operation,
        "status": status,
        "error": error,
        "duration_ms": round(duration_ms, 2) if duration_ms is not None else None,
        "request_hash": request_hash(provider, operation, safe_request),
        "request": safe_request,
        "response": safe_response,
        "metadata": metadata or {},
    }

    day_dir = _recordings_root() / provider / now.strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{now.strftime('%H%M%S')}_{operation}_{record_id[:8]}.json"
    path = day_dir / filename
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    index_path = day_dir / "_index.jsonl"
    with index_path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "id": record_id,
                    "timestamp": record["timestamp"],
                    "operation": operation,
                    "status": status,
                    "file": filename,
                    "request_hash": record["request_hash"],
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    return record_id


def _iter_record_files(
    provider: str | None = None,
    *,
    limit: int = 50,
) -> list[Path]:
    root = _recordings_root()
    if not root.exists():
        return []

    patterns: list[Path]
    if provider:
        base = root / provider
        patterns = sorted(base.glob("*/*.json"), reverse=True) if base.exists() else []
    else:
        patterns = sorted(root.glob("*/*/*.json"), reverse=True)

    files = [path for path in patterns if path.name != "_index.jsonl"]
    return files[:limit]


def list_recordings(
    *,
    provider: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return summary rows for recent recordings (newest first)."""
    summaries: list[dict[str, Any]] = []
    for path in _iter_record_files(provider, limit=limit):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        summaries.append(
            {
                "id": data.get("id"),
                "timestamp": data.get("timestamp"),
                "provider": data.get("provider"),
                "operation": data.get("operation"),
                "status": data.get("status"),
                "duration_ms": data.get("duration_ms"),
                "request_hash": data.get("request_hash"),
                "path": str(path.relative_to(_recordings_root())).replace("\\", "/"),
            }
        )
    return summaries


def get_recording(record_id: str) -> dict[str, Any] | None:
    root = _recordings_root()
    if not root.exists():
        return None
    matches = list(root.glob(f"*/*/*{record_id[:8]}*.json"))
    for path in matches:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("id") == record_id:
            data["path"] = str(path.relative_to(root)).replace("\\", "/")
            return data
    return None


def find_recording(
    provider: str,
    operation: str,
    request: Any,
) -> dict[str, Any] | None:
    """Lookup a prior recording by sanitized request hash (for mock replay)."""
    target = request_hash(provider, operation, request)
    for path in _iter_record_files(provider, limit=500):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (
            data.get("request_hash") == target
            and data.get("operation") == operation
            and data.get("status") == "success"
        ):
            data["path"] = str(path.relative_to(_recordings_root())).replace("\\", "/")
            return data
    return None
