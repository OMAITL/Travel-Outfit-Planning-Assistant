"""Volcengine OpenAPI V4 request signing (HMAC-SHA256)."""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime
from urllib.parse import quote

SERVICE = "cv"
VERSION = "2022-08-31"
REGION = "cn-north-1"
HOST = "visual.volcengineapi.com"


def sign_request(
    access_key: str,
    secret_key: str,
    *,
    method: str,
    query: dict[str, str],
    body: str,
) -> dict[str, str]:
    """Return signed headers for a Volcengine visual API request."""
    now = datetime.now(UTC)
    x_date = now.strftime("%Y%m%dT%H%M%SZ")
    short_date = now.strftime("%Y%m%d")
    body_hash = hashlib.sha256(body.encode()).hexdigest()

    canonical_headers = (
        f"content-type:application/json\n"
        f"host:{HOST}\n"
        f"x-content-sha256:{body_hash}\n"
        f"x-date:{x_date}\n"
    )
    signed_headers = "content-type;host;x-content-sha256;x-date"

    canonical_query = "&".join(
        f"{key}={quote(str(value), safe='')}" for key, value in sorted(query.items())
    )
    canonical_request = (
        f"{method}\n/\n{canonical_query}\n{canonical_headers}\n{signed_headers}\n{body_hash}"
    )

    credential_scope = f"{short_date}/{REGION}/{SERVICE}/request"
    string_to_sign = (
        "HMAC-SHA256\n"
        f"{x_date}\n"
        f"{credential_scope}\n"
        f"{hashlib.sha256(canonical_request.encode()).hexdigest()}"
    )

    signing_key = secret_key.encode()
    for part in (short_date, REGION, SERVICE, "request"):
        signing_key = hmac.new(signing_key, part.encode(), hashlib.sha256).digest()
    signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()

    authorization = (
        f"HMAC-SHA256 Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    return {
        "Authorization": authorization,
        "X-Date": x_date,
        "X-Content-Sha256": body_hash,
        "Content-Type": "application/json",
        "Host": HOST,
    }
