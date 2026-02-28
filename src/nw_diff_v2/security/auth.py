"""Authentication helpers for protected API routes."""

from __future__ import annotations

import base64
import binascii
import hmac
from typing import Optional

from fastapi import Header, HTTPException, status
from werkzeug.security import check_password_hash

from nw_diff_v2.config import settings


def _is_development() -> bool:
    return settings.env.lower() in {"dev", "development", "local", "test"}


def _decode_basic_credentials(authorization: str) -> Optional[tuple[str, str]]:
    """Decode Basic auth header into username/password pair."""
    if not authorization.startswith("Basic ") or len(authorization) < 7:
        return None
    encoded = authorization[6:]
    try:
        decoded = base64.b64decode(encoded).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return None
    if ":" not in decoded:
        return None
    username, password = decoded.split(":", 1)
    return username, password


def _verify_basic_auth(authorization: str) -> bool:
    """Validate HTTP Basic credentials against configured settings."""
    decoded = _decode_basic_credentials(authorization)
    if decoded is None:
        return False

    username, password = decoded
    expected_user = settings.nw_diff_basic_user
    if not expected_user or not hmac.compare_digest(username, expected_user):
        return False

    if settings.nw_diff_basic_password_hash:
        return check_password_hash(settings.nw_diff_basic_password_hash, password)
    plain_password = settings.nw_diff_basic_password
    if not plain_password:
        return False
    return hmac.compare_digest(password, plain_password)


def require_auth(authorization: Optional[str] = Header(default=None)) -> None:
    """
    Require bearer token for protected routes.

    Development-only bypass is allowed when NW_DIFF_API_TOKEN is unset.
    """
    expected_token = settings.nw_diff_api_token
    if not expected_token:
        if _is_development():
            return
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Server authentication is not configured",
        )

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    if authorization.startswith("Bearer "):
        token = authorization[7:]
        if hmac.compare_digest(token, expected_token):
            return
    elif authorization.startswith("Basic "):
        if _verify_basic_auth(authorization):
            return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )
