"""
Copyright 2025 NW-Diff Contributors
SPDX-License-Identifier: Apache-2.0

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

This file was created or modified with the assistance of an AI (Large Language Model).
Review required for correctness, security, and licensing.
"""

import base64
import binascii
import hmac
import logging
import os
from functools import wraps

from flask import jsonify, request
from werkzeug.security import check_password_hash

logger = logging.getLogger("nw-diff")


def _is_development_environment() -> bool:
    """Return True when running in an explicitly development-like environment."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    env = (
        os.environ.get("NW_DIFF_ENV")
        or os.environ.get("APP_ENV")
        or os.environ.get("FLASK_ENV")
        or ""
    )
    return env.lower() in {"dev", "development", "local", "test"}


# pylint: disable=too-many-return-statements
def _verify_basic_auth(auth_header: str) -> bool:
    """
    Verify HTTP Basic authentication credentials.

    Args:
        auth_header: The Authorization header value (e.g., "Basic base64string")

    Returns:
        True if credentials are valid, False otherwise
    """
    try:
        # Extract base64-encoded credentials
        # "Basic " is 6 characters, need at least 1 more for valid base64
        if not auth_header.startswith("Basic ") or len(auth_header) < 7:
            return False

        encoded_credentials = auth_header[6:]  # Remove "Basic " prefix

        # Decode base64
        try:
            decoded_bytes = base64.b64decode(encoded_credentials)
            decoded_str = decoded_bytes.decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            logger.warning("Failed to decode Basic auth credentials")
            return False

        # Parse username:password
        if ":" not in decoded_str:
            logger.warning("Invalid Basic auth format - missing colon separator")
            return False

        username, password = decoded_str.split(":", 1)

        # Get expected credentials from environment
        expected_user = os.environ.get("NW_DIFF_BASIC_USER")
        password_hash = os.environ.get("NW_DIFF_BASIC_PASSWORD_HASH")
        plain_password = os.environ.get("NW_DIFF_BASIC_PASSWORD")

        # Verify username with timing-safe comparison
        if not expected_user or not hmac.compare_digest(username, expected_user):
            return False

        # Verify password - prefer hash over plain (development fallback)
        if password_hash:
            # Production: verify against Werkzeug password hash only
            # Do not fall back to plain password if hash is configured
            return check_password_hash(password_hash, password)

        if plain_password:
            # Development fallback: verify against plain password
            # Only used when password_hash is not configured
            if hmac.compare_digest(password, plain_password):
                logger.warning(
                    "Basic auth succeeded with plain password - "
                    "use hashed password in production"
                )
                return True

        return False

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error verifying Basic auth: %s", str(e))
        return False


def require_api_token(f):
    """
    Decorator to require API token authentication for sensitive endpoints.
    Supports both Bearer token and HTTP Basic authentication.

    Bearer token: Authorization: Bearer <token>
    Basic auth: Authorization: Basic <base64(user:pass)>

    The expected token is read from NW_DIFF_API_TOKEN environment variable.
    Basic auth credentials are verified against NW_DIFF_BASIC_USER and
    NW_DIFF_BASIC_PASSWORD_HASH (or NW_DIFF_BASIC_PASSWORD for development).

    Returns 401 for missing or invalid tokens without leaking internal details.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        expected_token = os.environ.get("NW_DIFF_API_TOKEN")

        # If no token is configured, only allow bypass in development environments.
        if not expected_token:
            if _is_development_environment():
                logger.warning(
                    "NW_DIFF_API_TOKEN not set in development mode - "
                    "authentication bypassed for %s",
                    request.path,
                )
                return f(*args, **kwargs)
            logger.error(
                "NW_DIFF_API_TOKEN not set in non-development environment - "
                "blocking access to %s",
                request.path,
            )
            return jsonify({"error": "Server authentication is not configured"}), 503

        # Check Authorization header
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            logger.warning(
                "Unauthorized access attempt to %s - missing Authorization header",
                request.path,
            )
            return jsonify({"error": "Authentication required"}), 401

        # Try Bearer token authentication
        if auth_header.startswith("Bearer "):
            # Check for Bearer token format with at least one character after
            # "Bearer " is 7 characters, so we need at least 8 characters total
            if len(auth_header) < 8:
                logger.warning(
                    "Unauthorized access attempt to %s - invalid Authorization format",
                    request.path,
                )
                return jsonify({"error": "Authentication required"}), 401

            # Extract token (everything after "Bearer ")
            token = auth_header[7:]  # Remove "Bearer " prefix

            # Use constant-time comparison to prevent timing attacks
            # hmac.compare_digest safely handles tokens of different lengths
            if hmac.compare_digest(token, expected_token):
                # Token is valid, proceed with the request
                return f(*args, **kwargs)

        # Try Basic authentication as fallback
        elif auth_header.startswith("Basic "):
            if _verify_basic_auth(auth_header):
                # Basic auth is valid, proceed with the request
                return f(*args, **kwargs)

        # All authentication methods failed
        logger.warning(
            "Unauthorized access attempt to %s - invalid credentials", request.path
        )
        return jsonify({"error": "Authentication required"}), 401

    return decorated_function
