"""Authentication helpers for protected API routes."""

from __future__ import annotations

# pylint: disable=too-many-return-statements

import base64
import binascii
import hmac
from typing import Optional

from fastapi import Header, HTTPException, status
from werkzeug.security import check_password_hash

from nw_diff_v2.config import settings


def _is_development() -> bool:
    return settings.env.lower() in {"dev", "development", "local", "test"}


def _verify_basic_auth(
    authorization: str,
) -> bool:
    """Validate HTTP Basic credentials against configured settings."""
    if not authorization.startswith("Basic ") or len(authorization) < 7:
        return False
    try:
        encoded = authorization[6:]
        decoded = base64.b64decode(encoded).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return False
    if ":" not in decoded:
        return False

    username, password = decoded.split(":", 1)
    expected_user = settings.nw_diff_basic_user
    if not expected_user or not hmac.compare_digest(username, expected_user):
        return False

    if settings.nw_diff_basic_password_hash:
        return check_password_hash(settings.nw_diff_basic_password_hash, password)
    if settings.nw_diff_basic_password:
        return hmac.compare_digest(password, settings.nw_diff_basic_password)
    return False


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
