"""Input validation helpers for v2 APIs."""

from __future__ import annotations

import re

_SAFE_HOST_RE = re.compile(r"^[a-zA-Z0-9._-]+$")


def validate_hostname(hostname: str) -> bool:
    """Return True if hostname is safe for artifact lookup paths."""
    if not hostname:
        return False
    if ".." in hostname or "/" in hostname or "\\" in hostname:
        return False
    return bool(_SAFE_HOST_RE.match(hostname))
