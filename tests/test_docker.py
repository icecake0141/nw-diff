"""
Copyright 2025 NW-Diff Contributors
SPDX-License-Identifier: Apache-2.0

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

This file was created or modified with the assistance of an AI (Large Language Model).
Review required for correctness, security, and licensing.

Integration tests for Docker deployment with HTTPS and Basic Authentication.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _docker_build_available() -> bool:
    """Return True when docker daemon is reachable for build tests."""
    docker_exists = (
        subprocess.run(["which", "docker"], capture_output=True, check=False).returncode
        == 0
    )
    if not docker_exists:
        return False
    return (
        subprocess.run(["docker", "info"], capture_output=True, check=False).returncode
        == 0
    )


def test_dockerfile_exists() -> None:
    """Verify Dockerfile exists in repository root."""
    dockerfile = PROJECT_ROOT / "Dockerfile"
    assert dockerfile.exists(), "Dockerfile should exist in repository root"
    assert dockerfile.is_file(), "Dockerfile should be a regular file"


def test_docker_compose_exists() -> None:
    """Verify docker-compose.yml exists in repository root."""
    compose_file = PROJECT_ROOT / "docker-compose.yml"
    assert compose_file.exists(), "docker-compose.yml should exist in repository root"
    assert compose_file.is_file(), "docker-compose.yml should be a regular file"


def test_nginx_config_exists() -> None:
    """Verify nginx configuration exists."""
    nginx_conf = PROJECT_ROOT / "docker" / "nginx.conf"
    assert nginx_conf.exists(), "nginx.conf should exist in docker directory"
    assert nginx_conf.is_file(), "nginx.conf should be a regular file"


def test_helper_scripts_exist() -> None:
    """Verify helper scripts exist and are executable."""
    scripts_dir = PROJECT_ROOT / "scripts"
    assert scripts_dir.exists(), "scripts directory should exist"

    mk_htpasswd = scripts_dir / "mk-htpasswd.sh"
    assert mk_htpasswd.exists(), "mk-htpasswd.sh should exist"
    assert mk_htpasswd.stat().st_mode & 0o111, "mk-htpasswd.sh should be executable"

    mk_certs = scripts_dir / "mk-certs.sh"
    assert mk_certs.exists(), "mk-certs.sh should exist"
    assert mk_certs.stat().st_mode & 0o111, "mk-certs.sh should be executable"


def test_init_script_exists() -> None:
    """Verify automated init script exists and is executable."""
    init_script = PROJECT_ROOT / "docker" / "nginx" / "init-certs-and-htpasswd.sh"
    assert init_script.exists(), "init-certs-and-htpasswd.sh should exist"
    assert init_script.is_file(), "init-certs-and-htpasswd.sh should be a regular file"
    assert (
        init_script.stat().st_mode & 0o111
    ), "init-certs-and-htpasswd.sh should be executable"


def test_init_script_has_license_header() -> None:
    """Verify init script contains proper license header."""
    init_script = PROJECT_ROOT / "docker" / "nginx" / "init-certs-and-htpasswd.sh"
    content = init_script.read_text(encoding="utf-8")
    assert "Apache-2.0" in content, "init script should have Apache-2.0 license"
    assert (
        "SPDX-License-Identifier" in content
    ), "init script should have SPDX identifier"


def test_init_script_has_llm_attribution() -> None:
    """Verify init script contains LLM attribution comment."""
    init_script = PROJECT_ROOT / "docker" / "nginx" / "init-certs-and-htpasswd.sh"
    content = init_script.read_text(encoding="utf-8")
    assert "Large Language Model" in content, "init script should have LLM attribution"


def test_init_script_has_security_warnings() -> None:
    """Verify init script contains appropriate security warnings."""
    init_script = PROJECT_ROOT / "docker" / "nginx" / "init-certs-and-htpasswd.sh"
    content = init_script.read_text(encoding="utf-8")
    assert (
        "self-signed" in content.lower()
    ), "init script should warn about self-signed certificates"
    assert (
        "production" in content.lower()
    ), "init script should have production guidance"
    assert (
        "let's encrypt" in content.lower() or "letsencrypt" in content.lower()
    ), "init script should mention Let's Encrypt"


def test_env_example_exists() -> None:
    """Verify .env.example exists."""
    env_example = PROJECT_ROOT / ".env.example"
    assert env_example.exists(), ".env.example should exist in repository root"
    assert env_example.is_file(), ".env.example should be a regular file"


def test_dockerfile_has_license_header() -> None:
    """Verify Dockerfile contains proper license header."""
    dockerfile = PROJECT_ROOT / "Dockerfile"
    content = dockerfile.read_text(encoding="utf-8")
    assert "Apache-2.0" in content, "Dockerfile should have Apache-2.0 license"
    assert (
        "SPDX-License-Identifier" in content
    ), "Dockerfile should have SPDX identifier"


def test_dockerfile_has_llm_attribution() -> None:
    """Verify Dockerfile contains LLM attribution comment."""
    dockerfile = PROJECT_ROOT / "Dockerfile"
    content = dockerfile.read_text(encoding="utf-8")
    assert "Large Language Model" in content, "Dockerfile should have LLM attribution"


def test_docker_compose_has_license_header() -> None:
    """Verify docker-compose.yml contains proper license header."""
    compose_file = PROJECT_ROOT / "docker-compose.yml"
    content = compose_file.read_text(encoding="utf-8")
    assert "Apache-2.0" in content, "docker-compose.yml should have Apache-2.0 license"
    assert (
        "SPDX-License-Identifier" in content
    ), "docker-compose.yml should have SPDX identifier"


def test_nginx_conf_has_license_header() -> None:
    """Verify nginx.conf contains proper license header."""
    nginx_conf = PROJECT_ROOT / "docker" / "nginx.conf"
    content = nginx_conf.read_text(encoding="utf-8")
    assert "Apache-2.0" in content, "nginx.conf should have Apache-2.0 license"
    assert (
        "SPDX-License-Identifier" in content
    ), "nginx.conf should have SPDX identifier"


def test_nginx_conf_has_basic_auth_config() -> None:
    """Verify nginx.conf contains Basic Authentication configuration."""
    nginx_conf = PROJECT_ROOT / "docker" / "nginx.conf"
    content = nginx_conf.read_text(encoding="utf-8")
    assert "auth_basic" in content, "nginx.conf should have auth_basic directive"
    assert (
        "auth_basic_user_file" in content
    ), "nginx.conf should have auth_basic_user_file directive"
    assert ".htpasswd" in content, "nginx.conf should reference .htpasswd file"


def test_nginx_conf_has_tls_config() -> None:
    """Verify nginx.conf contains TLS/SSL configuration."""
    nginx_conf = PROJECT_ROOT / "docker" / "nginx.conf"
    content = nginx_conf.read_text(encoding="utf-8")
    assert "ssl_certificate" in content, "nginx.conf should have ssl_certificate"
    assert (
        "ssl_certificate_key" in content
    ), "nginx.conf should have ssl_certificate_key"
    assert "listen 443 ssl" in content, "nginx.conf should listen on port 443 with SSL"
    assert (
        "TLSv1.2" in content or "TLSv1.3" in content
    ), "nginx.conf should specify TLS versions"


def test_nginx_conf_has_http_to_https_redirect() -> None:
    """Verify nginx.conf redirects HTTP to HTTPS."""
    nginx_conf = PROJECT_ROOT / "docker" / "nginx.conf"
    content = nginx_conf.read_text(encoding="utf-8")
    assert "listen 80" in content, "nginx.conf should listen on port 80"
    assert "return 301 https://" in content, "nginx.conf should redirect HTTP to HTTPS"


def test_nginx_conf_has_security_headers() -> None:
    """Verify nginx.conf includes security headers."""
    nginx_conf = PROJECT_ROOT / "docker" / "nginx.conf"
    content = nginx_conf.read_text(encoding="utf-8")
    assert "X-Frame-Options" in content, "nginx.conf should set X-Frame-Options header"
    assert (
        "X-Content-Type-Options" in content
    ), "nginx.conf should set X-Content-Type-Options header"
    assert (
        "X-XSS-Protection" in content
    ), "nginx.conf should set X-XSS-Protection header"


def test_nginx_conf_has_hsts_documentation() -> None:
    """Verify nginx.conf has proper HSTS documentation and warnings."""
    nginx_conf = PROJECT_ROOT / "docker" / "nginx.conf"
    content = nginx_conf.read_text(encoding="utf-8")
    assert (
        "Strict-Transport-Security" in content
    ), "nginx.conf should reference HSTS header"
    assert (
        "self-signed" in content.lower()
    ), "nginx.conf should warn about self-signed certificates"
    assert "production" in content.lower(), "nginx.conf should have production guidance"


def test_nginx_conf_enforces_modern_tls() -> None:
    """Verify nginx.conf enforces only modern TLS versions."""
    nginx_conf = PROJECT_ROOT / "docker" / "nginx.conf"
    content = nginx_conf.read_text(encoding="utf-8")
    assert "TLSv1.2" in content, "nginx.conf should support TLSv1.2"
    assert "TLSv1.3" in content, "nginx.conf should support TLSv1.3"
    # Check that the ssl_protocols directive only includes modern versions
    # Look for the actual directive, not comments
    ssl_protocols_match = re.search(r"ssl_protocols\s+([^;]+);", content)
    assert ssl_protocols_match, "nginx.conf should have ssl_protocols directive"
    protocols = ssl_protocols_match.group(1).strip()

    # Verify exactly TLSv1.2 and TLSv1.3 are present using regex
    assert re.search(r"\bTLSv1\.2\b", protocols), "ssl_protocols should include TLSv1.2"
    assert re.search(r"\bTLSv1\.3\b", protocols), "ssl_protocols should include TLSv1.3"

    # Ensure old versions are not in the actual directive using word boundaries
    assert not re.search(
        r"\bTLSv1\.1\b", protocols
    ), "ssl_protocols should not include TLSv1.1"
    assert not re.search(
        r"\bTLSv1\.0\b|\bTLSv1\b(?!\.\d)", protocols
    ), "ssl_protocols should not include TLSv1.0"


def test_nginx_conf_has_strong_ciphers() -> None:
    """Verify nginx.conf uses strong cipher suites."""
    nginx_conf = PROJECT_ROOT / "docker" / "nginx.conf"
    content = nginx_conf.read_text(encoding="utf-8")
    assert "ssl_ciphers" in content, "nginx.conf should define ssl_ciphers"
    assert (
        "ECDHE" in content
    ), "nginx.conf should prefer forward secrecy ciphers (ECDHE)"
    assert "GCM" in content, "nginx.conf should include modern AEAD ciphers (GCM)"


def test_dockerfile_uses_non_root_user() -> None:
    """Verify Dockerfile creates and uses a non-root user."""
    dockerfile = PROJECT_ROOT / "Dockerfile"
    content = dockerfile.read_text(encoding="utf-8")
    assert (
        "useradd" in content or "adduser" in content
    ), "Dockerfile should create a user"
    assert "USER" in content, "Dockerfile should switch to non-root user"


def test_dockerfile_multi_stage_build() -> None:
    """Verify Dockerfile uses multi-stage build for efficiency."""
    dockerfile = PROJECT_ROOT / "Dockerfile"
    content = dockerfile.read_text(encoding="utf-8")
    assert "FROM" in content, "Dockerfile should have FROM instructions"
    # Count FROM instructions to verify multi-stage
    from_count = content.count("FROM ")
    assert from_count >= 2, "Dockerfile should use multi-stage build"


def test_dockerfile_has_healthcheck() -> None:
    """Verify Dockerfile includes health check."""
    dockerfile = PROJECT_ROOT / "Dockerfile"
    content = dockerfile.read_text(encoding="utf-8")
    assert "HEALTHCHECK" in content, "Dockerfile should have HEALTHCHECK instruction"


def test_docker_compose_has_volumes() -> None:
    """Verify docker-compose.yml defines persistent volumes."""
    compose_file = PROJECT_ROOT / "docker-compose.yml"
    content = compose_file.read_text(encoding="utf-8")
    assert "volumes:" in content, "docker-compose.yml should define volumes"
    assert "nw-diff-logs" in content, "docker-compose.yml should have logs volume"


def test_docker_compose_has_networks() -> None:
    """Verify docker-compose.yml defines networks."""
    compose_file = PROJECT_ROOT / "docker-compose.yml"
    content = compose_file.read_text(encoding="utf-8")
    assert "networks:" in content, "docker-compose.yml should define networks"


@pytest.mark.skipif(
    not _docker_build_available(),
    reason="Docker daemon not available or not accessible",
)
def test_dockerfile_builds_successfully() -> None:
    """Test that Dockerfile builds successfully.

    In CI environments with SSL interception, the build may require
    SKIP_PIP_SSL_VERIFY=1 to bypass certificate verification.
    """
    # Try building without SSL workaround first
    result = subprocess.run(
        ["docker", "build", "-t", "nw-diff:test", "."],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )

    # If build failed due to SSL issues, retry with workaround
    if result.returncode != 0 and "SSL" in result.stderr:
        result = subprocess.run(
            [
                "docker",
                "build",
                "--build-arg",
                "SKIP_PIP_SSL_VERIFY=1",
                "-t",
                "nw-diff:test",
                ".",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )

    assert result.returncode == 0, f"Docker build failed: {result.stderr}"


def test_gitignore_excludes_docker_secrets() -> None:
    """Verify .gitignore excludes Docker secrets and generated files."""
    gitignore = PROJECT_ROOT / ".gitignore"
    content = gitignore.read_text(encoding="utf-8")
    assert ".htpasswd" in content, ".gitignore should exclude .htpasswd file"
    assert (
        "certs" in content or "docker/certs" in content
    ), ".gitignore should exclude certificate directory"


def test_integration_workflow_exists() -> None:
    """Verify integration workflow file exists."""
    workflow = PROJECT_ROOT / ".github" / "workflows" / "integration.yml"
    assert workflow.exists(), "integration.yml should exist in .github/workflows"
    assert workflow.is_file(), "integration.yml should be a regular file"


def test_integration_workflow_has_license_header() -> None:
    """Verify integration workflow contains proper license header."""
    workflow = PROJECT_ROOT / ".github" / "workflows" / "integration.yml"
    content = workflow.read_text(encoding="utf-8")
    assert "Apache-2.0" in content, "integration.yml should have Apache-2.0 license"
    assert (
        "SPDX-License-Identifier" in content
    ), "integration.yml should have SPDX identifier"


def test_integration_workflow_has_llm_attribution() -> None:
    """Verify integration workflow contains LLM attribution comment."""
    workflow = PROJECT_ROOT / ".github" / "workflows" / "integration.yml"
    content = workflow.read_text(encoding="utf-8")
    assert (
        "Large Language Model" in content
    ), "integration.yml should have LLM attribution"


def test_integration_test_script_exists() -> None:
    """Verify integration test script exists and is executable."""
    script = PROJECT_ROOT / "scripts" / "test-integration.sh"
    assert script.exists(), "test-integration.sh should exist in scripts directory"
    assert script.is_file(), "test-integration.sh should be a regular file"
    assert script.stat().st_mode & 0o111, "test-integration.sh should be executable"


def test_integration_test_script_has_license_header() -> None:
    """Verify integration test script contains proper license header."""
    script = PROJECT_ROOT / "scripts" / "test-integration.sh"
    content = script.read_text(encoding="utf-8")
    assert "Apache-2.0" in content, "test-integration.sh should have Apache-2.0 license"
    assert (
        "SPDX-License-Identifier" in content
    ), "test-integration.sh should have SPDX identifier"


def test_integration_test_script_has_llm_attribution() -> None:
    """Verify integration test script contains LLM attribution comment."""
    script = PROJECT_ROOT / "scripts" / "test-integration.sh"
    content = script.read_text(encoding="utf-8")
    assert (
        "Large Language Model" in content
    ), "test-integration.sh should have LLM attribution"


def test_integration_workflow_tests_https() -> None:
    """Verify integration workflow includes HTTPS testing."""
    workflow = PROJECT_ROOT / ".github" / "workflows" / "integration.yml"
    content = workflow.read_text(encoding="utf-8")
    assert "https" in content.lower(), "workflow should test HTTPS"
    assert (
        "ssl" in content.lower() or "tls" in content.lower()
    ), "workflow should reference SSL/TLS"


def test_integration_workflow_tests_auth() -> None:
    """Verify integration workflow includes authentication testing."""
    workflow = PROJECT_ROOT / ".github" / "workflows" / "integration.yml"
    content = workflow.read_text(encoding="utf-8")
    assert (
        "auth" in content.lower() or "htpasswd" in content.lower()
    ), "workflow should test authentication"
    assert "NW_DIFF_BASIC_USER" in content, "workflow should set basic auth user"
    assert (
        "NW_DIFF_BASIC_PASSWORD" in content
    ), "workflow should set basic auth password"


def test_integration_workflow_generates_certificates() -> None:
    """Verify integration workflow generates certificates."""
    workflow = PROJECT_ROOT / ".github" / "workflows" / "integration.yml"
    content = workflow.read_text(encoding="utf-8")
    assert "init-certs-and-htpasswd.sh" in content, "workflow should run init script"
    assert "cert" in content.lower(), "workflow should mention certificates"


def test_integration_workflow_uses_docker_compose() -> None:
    """Verify integration workflow uses docker compose (CLI plugin or standalone)."""
    workflow = PROJECT_ROOT / ".github" / "workflows" / "integration.yml"
    content = workflow.read_text(encoding="utf-8")
    # Accept both "docker-compose" (legacy) and "docker compose" (CLI plugin)
    assert (
        "docker-compose" in content or "docker compose" in content
    ), "workflow should use docker-compose or docker compose"
    assert (
        "docker-compose up" in content
        or "docker-compose build" in content
        or "docker compose up" in content
        or "docker compose build" in content
    ), "workflow should build/start stack"
    assert (
        "docker-compose down" in content or "docker compose down" in content
    ), "workflow should clean up docker compose stack"


def test_integration_test_script_tests_http_redirect() -> None:
    """Verify integration test script tests HTTP to HTTPS redirect."""
    script = PROJECT_ROOT / "scripts" / "test-integration.sh"
    content = script.read_text(encoding="utf-8")
    assert "redirect" in content.lower(), "script should test HTTP redirect"
    assert "301" in content or "302" in content, "script should check redirect status"


def test_integration_test_script_tests_auth_required() -> None:
    """Verify integration test script tests that auth is required."""
    script = PROJECT_ROOT / "scripts" / "test-integration.sh"
    content = script.read_text(encoding="utf-8")
    assert "401" in content, "script should check for 401 unauthorized"
    assert (
        "basic" in content.lower() and "auth" in content.lower()
    ), "script should test basic auth"


def test_integration_test_script_tests_bearer_token() -> None:
    """Verify integration test script tests Bearer token authentication."""
    script = PROJECT_ROOT / "scripts" / "test-integration.sh"
    content = script.read_text(encoding="utf-8")
    assert (
        "bearer" in content.lower() or "Authorization: Bearer" in content
    ), "script should test Bearer token"
    assert "API_TOKEN" in content, "script should use API token"


def test_readme_has_ci_badges() -> None:
    """Verify README includes CI status badges."""
    readme = PROJECT_ROOT / "README.md"
    content = readme.read_text(encoding="utf-8")
    assert "badge.svg" in content, "README should have CI badge"
    assert "workflows/ci.yml" in content, "README should link to CI workflow"
    assert (
        "workflows/integration.yml" in content
    ), "README should link to integration workflow"


def test_readme_documents_integration_tests() -> None:
    """Verify README documents integration testing."""
    readme = PROJECT_ROOT / "README.md"
    content = readme.read_text(encoding="utf-8")
    assert (
        "integration test" in content.lower()
    ), "README should mention integration tests"
    assert "test-integration.sh" in content, "README should reference test script"
    assert "https" in content.lower(), "README should document HTTPS testing"
    assert (
        "docker-compose" in content.lower()
    ), "README should document Docker Compose testing"
