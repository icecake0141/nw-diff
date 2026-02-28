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

from __future__ import annotations

import base64
import sys
from pathlib import Path

from werkzeug.security import generate_password_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nw_diff import app  # pylint: disable=wrong-import-position


def _make_basic_auth_header(username: str, password: str) -> str:
    """Helper to create Basic auth header."""
    credentials = f"{username}:{password}"
    encoded = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
    return f"Basic {encoded}"


# --- Tests for Basic Authentication with plain password (development) ---


def test_basic_auth_plain_password_success(monkeypatch) -> None:
    """Test Basic auth succeeds with correct plain password credentials."""
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_token")
    monkeypatch.setenv("NW_DIFF_BASIC_USER", "testuser")
    monkeypatch.setenv("NW_DIFF_BASIC_PASSWORD", "testpass")

    with app.app.test_client() as client:
        response = client.get(
            "/api/logs",
            headers={"Authorization": _make_basic_auth_header("testuser", "testpass")},
        )

    # Should not be 401 (will be 200 or other error)
    assert response.status_code != 401


def test_basic_auth_plain_password_wrong_username(monkeypatch) -> None:
    """Test Basic auth fails with wrong username."""
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_token")
    monkeypatch.setenv("NW_DIFF_BASIC_USER", "testuser")
    monkeypatch.setenv("NW_DIFF_BASIC_PASSWORD", "testpass")

    with app.app.test_client() as client:
        response = client.get(
            "/api/logs",
            headers={"Authorization": _make_basic_auth_header("wronguser", "testpass")},
        )

    assert response.status_code == 401
    assert response.json is not None
    assert response.json["error"] == "Authentication required"


def test_basic_auth_plain_password_wrong_password(monkeypatch) -> None:
    """Test Basic auth fails with wrong password."""
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_token")
    monkeypatch.setenv("NW_DIFF_BASIC_USER", "testuser")
    monkeypatch.setenv("NW_DIFF_BASIC_PASSWORD", "testpass")

    with app.app.test_client() as client:
        response = client.get(
            "/api/logs",
            headers={"Authorization": _make_basic_auth_header("testuser", "wrongpass")},
        )

    assert response.status_code == 401
    assert response.json is not None
    assert response.json["error"] == "Authentication required"


# --- Tests for Basic Authentication with hashed password (production) ---


def test_basic_auth_hashed_password_success(monkeypatch) -> None:
    """Test Basic auth succeeds with correct hashed password credentials."""
    password_hash = generate_password_hash("securepass", method="pbkdf2:sha256")
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_token")
    monkeypatch.setenv("NW_DIFF_BASIC_USER", "admin")
    monkeypatch.setenv("NW_DIFF_BASIC_PASSWORD_HASH", password_hash)

    with app.app.test_client() as client:
        response = client.get(
            "/api/logs",
            headers={"Authorization": _make_basic_auth_header("admin", "securepass")},
        )

    # Should not be 401
    assert response.status_code != 401


def test_basic_auth_hashed_password_wrong_password(monkeypatch) -> None:
    """Test Basic auth fails with wrong password against hash."""
    password_hash = generate_password_hash("securepass", method="pbkdf2:sha256")
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_token")
    monkeypatch.setenv("NW_DIFF_BASIC_USER", "admin")
    monkeypatch.setenv("NW_DIFF_BASIC_PASSWORD_HASH", password_hash)

    with app.app.test_client() as client:
        response = client.get(
            "/api/logs",
            headers={"Authorization": _make_basic_auth_header("admin", "wrongpass")},
        )

    assert response.status_code == 401


def test_basic_auth_prefers_hash_over_plain(monkeypatch) -> None:
    """Test that hashed password is used exclusively when configured."""
    password_hash = generate_password_hash("hashpass", method="pbkdf2:sha256")
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_token")
    monkeypatch.setenv("NW_DIFF_BASIC_USER", "admin")
    monkeypatch.setenv("NW_DIFF_BASIC_PASSWORD_HASH", password_hash)
    monkeypatch.setenv("NW_DIFF_BASIC_PASSWORD", "plainpass")

    with app.app.test_client() as client:
        # Should succeed with hash password
        response = client.get(
            "/api/logs",
            headers={"Authorization": _make_basic_auth_header("admin", "hashpass")},
        )
        assert response.status_code != 401

        # Should fail with plain password - no fallback when hash is configured
        response = client.get(
            "/api/logs",
            headers={"Authorization": _make_basic_auth_header("admin", "plainpass")},
        )
        assert response.status_code == 401


# --- Tests for Bearer token backward compatibility ---


def test_bearer_token_still_works_with_basic_auth_configured(monkeypatch) -> None:
    """Test that Bearer token auth still works when Basic auth is configured."""
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_token")
    monkeypatch.setenv("NW_DIFF_BASIC_USER", "admin")
    monkeypatch.setenv("NW_DIFF_BASIC_PASSWORD", "testpass")

    with app.app.test_client() as client:
        response = client.get(
            "/api/logs",
            headers={"Authorization": "Bearer test_token"},
        )

    # Bearer token should still work
    assert response.status_code != 401


def test_invalid_bearer_token_with_basic_auth_configured(monkeypatch) -> None:
    """Test that invalid Bearer token is rejected even with Basic auth configured."""
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_token")
    monkeypatch.setenv("NW_DIFF_BASIC_USER", "admin")
    monkeypatch.setenv("NW_DIFF_BASIC_PASSWORD", "testpass")

    with app.app.test_client() as client:
        response = client.get(
            "/api/logs",
            headers={"Authorization": "Bearer wrong_token"},
        )

    assert response.status_code == 401


# --- Tests for legacy behavior (no NW_DIFF_API_TOKEN set) ---


def test_basic_auth_not_enforced_when_no_api_token(monkeypatch) -> None:
    """Test that Basic auth is not enforced when NW_DIFF_API_TOKEN is not set."""
    monkeypatch.delenv("NW_DIFF_API_TOKEN", raising=False)
    monkeypatch.setenv("NW_DIFF_ENV", "development")
    monkeypatch.setenv("NW_DIFF_BASIC_USER", "admin")
    monkeypatch.setenv("NW_DIFF_BASIC_PASSWORD", "testpass")

    with app.app.test_client() as client:
        # Should work without any auth header
        response = client.get("/api/logs")
        assert response.status_code != 401


def test_auth_fails_without_api_token_in_production(monkeypatch) -> None:
    """No-token mode should be blocked outside development."""
    monkeypatch.delenv("NW_DIFF_API_TOKEN", raising=False)
    monkeypatch.setenv("NW_DIFF_ENV", "production")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    with app.app.test_client() as client:
        response = client.get("/api/logs")

    assert response.status_code == 503
    assert response.json is not None
    assert response.json["error"] == "Server authentication is not configured"


# --- Tests for invalid Basic auth formats ---


def test_basic_auth_invalid_base64(monkeypatch) -> None:
    """Test Basic auth with invalid base64 encoding."""
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_token")
    monkeypatch.setenv("NW_DIFF_BASIC_USER", "admin")
    monkeypatch.setenv("NW_DIFF_BASIC_PASSWORD", "testpass")

    with app.app.test_client() as client:
        response = client.get(
            "/api/logs",
            headers={"Authorization": "Basic !!!invalid-base64!!!"},
        )

    assert response.status_code == 401


def test_basic_auth_missing_colon_separator(monkeypatch) -> None:
    """Test Basic auth with credentials missing colon separator."""
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_token")
    monkeypatch.setenv("NW_DIFF_BASIC_USER", "admin")
    monkeypatch.setenv("NW_DIFF_BASIC_PASSWORD", "testpass")

    # Create credentials without colon
    credentials = "adminonly"
    encoded = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")

    with app.app.test_client() as client:
        response = client.get(
            "/api/logs",
            headers={"Authorization": f"Basic {encoded}"},
        )

    assert response.status_code == 401


def test_basic_auth_empty_password(monkeypatch) -> None:
    """Test Basic auth with empty password."""
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_token")
    monkeypatch.setenv("NW_DIFF_BASIC_USER", "admin")
    monkeypatch.setenv("NW_DIFF_BASIC_PASSWORD", "testpass")

    with app.app.test_client() as client:
        response = client.get(
            "/api/logs",
            headers={"Authorization": _make_basic_auth_header("admin", "")},
        )

    assert response.status_code == 401


def test_basic_auth_empty_username(monkeypatch) -> None:
    """Test Basic auth with empty username."""
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_token")
    monkeypatch.setenv("NW_DIFF_BASIC_USER", "admin")
    monkeypatch.setenv("NW_DIFF_BASIC_PASSWORD", "testpass")

    with app.app.test_client() as client:
        response = client.get(
            "/api/logs",
            headers={"Authorization": _make_basic_auth_header("", "testpass")},
        )

    assert response.status_code == 401


# --- Tests for Basic auth without required environment variables ---


def test_basic_auth_fails_when_user_not_configured(monkeypatch) -> None:
    """Test Basic auth fails when NW_DIFF_BASIC_USER is not set."""
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_token")
    monkeypatch.delenv("NW_DIFF_BASIC_USER", raising=False)
    monkeypatch.setenv("NW_DIFF_BASIC_PASSWORD", "testpass")

    with app.app.test_client() as client:
        response = client.get(
            "/api/logs",
            headers={"Authorization": _make_basic_auth_header("admin", "testpass")},
        )

    assert response.status_code == 401


def test_basic_auth_fails_when_password_not_configured(monkeypatch) -> None:
    """Test Basic auth fails when neither password nor hash is set."""
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_token")
    monkeypatch.setenv("NW_DIFF_BASIC_USER", "admin")
    monkeypatch.delenv("NW_DIFF_BASIC_PASSWORD", raising=False)
    monkeypatch.delenv("NW_DIFF_BASIC_PASSWORD_HASH", raising=False)

    with app.app.test_client() as client:
        response = client.get(
            "/api/logs",
            headers={"Authorization": _make_basic_auth_header("admin", "testpass")},
        )

    assert response.status_code == 401


# --- Tests for different protected endpoints ---


def test_basic_auth_works_on_capture_endpoint(tmp_path: Path, monkeypatch) -> None:
    """Test Basic auth works on /capture endpoint."""
    # pylint: disable=import-outside-toplevel
    from nw_diff import devices

    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_token")
    monkeypatch.setenv("NW_DIFF_BASIC_USER", "admin")
    monkeypatch.setenv("NW_DIFF_BASIC_PASSWORD", "testpass")

    with app.app.test_client() as client:
        response = client.post(
            "/capture/origin/router1",
            headers={"Authorization": _make_basic_auth_header("admin", "testpass")},
        )

    # Should not be 401 (will be error due to device connection)
    assert response.status_code != 401


def test_basic_auth_works_on_export_endpoint(tmp_path: Path, monkeypatch) -> None:
    """Test Basic auth works on /api/export endpoint."""
    # pylint: disable=import-outside-toplevel
    from nw_diff import devices, storage

    hosts_csv = tmp_path / "hosts.csv"
    hosts_csv.write_text(
        """host,ip,username,port,model\nrouter1,10.0.0.1,admin,22,cisco\n""",
        encoding="utf-8",
    )
    monkeypatch.setattr(devices, "HOSTS_CSV", str(hosts_csv))
    monkeypatch.setattr(storage, "ORIGIN_DIR", str(tmp_path / "origin"))
    monkeypatch.setattr(storage, "DEST_DIR", str(tmp_path / "dest"))
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_token")
    monkeypatch.setenv("NW_DIFF_BASIC_USER", "admin")
    monkeypatch.setenv("NW_DIFF_BASIC_PASSWORD", "testpass")

    with app.app.test_client() as client:
        response = client.get(
            "/api/export/router1",
            headers={"Authorization": _make_basic_auth_header("admin", "testpass")},
        )

    # Should not be 401
    assert response.status_code != 401


# --- Tests for error message consistency ---


def test_basic_auth_error_message_does_not_leak_details(monkeypatch) -> None:
    """Test that Basic auth errors don't leak sensitive information."""
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_token")
    monkeypatch.setenv("NW_DIFF_BASIC_USER", "admin")
    monkeypatch.setenv("NW_DIFF_BASIC_PASSWORD", "secretpass")

    with app.app.test_client() as client:
        response = client.get(
            "/api/logs",
            headers={"Authorization": _make_basic_auth_header("admin", "wrongpass")},
        )

    assert response.status_code == 401
    json_data = response.get_json()
    assert json_data is not None
    # Error message should be generic
    assert json_data["error"] == "Authentication required"
    # Should not leak environment variable names or values
    assert "NW_DIFF_BASIC_USER" not in str(json_data)
    assert "NW_DIFF_BASIC_PASSWORD" not in str(json_data)
    assert "admin" not in str(json_data)
    assert "secretpass" not in str(json_data)


# --- Tests for username/password with special characters ---


def test_basic_auth_username_with_special_chars(monkeypatch) -> None:
    """Test Basic auth with username containing special characters."""
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_token")
    monkeypatch.setenv("NW_DIFF_BASIC_USER", "user@example.com")
    monkeypatch.setenv("NW_DIFF_BASIC_PASSWORD", "testpass")

    with app.app.test_client() as client:
        response = client.get(
            "/api/logs",
            headers={
                "Authorization": _make_basic_auth_header("user@example.com", "testpass")
            },
        )

    assert response.status_code != 401


def test_basic_auth_password_with_special_chars(monkeypatch) -> None:
    """Test Basic auth with password containing special characters."""
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_token")
    monkeypatch.setenv("NW_DIFF_BASIC_USER", "admin")
    monkeypatch.setenv("NW_DIFF_BASIC_PASSWORD", "p@ss:w0rd!#$")

    with app.app.test_client() as client:
        response = client.get(
            "/api/logs",
            headers={"Authorization": _make_basic_auth_header("admin", "p@ss:w0rd!#$")},
        )

    assert response.status_code != 401


def test_basic_auth_password_with_colon(monkeypatch) -> None:
    """Test Basic auth with password containing colon character."""
    monkeypatch.setenv("NW_DIFF_API_TOKEN", "test_token")
    monkeypatch.setenv("NW_DIFF_BASIC_USER", "admin")
    monkeypatch.setenv("NW_DIFF_BASIC_PASSWORD", "pass:with:colons")

    with app.app.test_client() as client:
        response = client.get(
            "/api/logs",
            headers={
                "Authorization": _make_basic_auth_header("admin", "pass:with:colons")
            },
        )

    assert response.status_code != 401
