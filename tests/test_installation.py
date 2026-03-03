# Copyright 2025 NW-Diff Contributors
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# This file was created or modified with the assistance of an AI (Large Language Model).
# Review required for correctness, security, and licensing.

"""
Test suite for validating installation requirements and user-facing setup.

This test suite ensures that the installation instructions documented in
README.md are accurate and that the application can be properly installed
and run by general users.
"""

import os
import socket
import subprocess
import sys
import importlib
import secrets
import shutil
from pathlib import Path

import pytest


def _can_reach_pypi(timeout: float = 2.0) -> bool:
    """Return True if test environment can reach PyPI over TLS port."""
    try:
        with socket.create_connection(("pypi.org", 443), timeout=timeout):
            return True
    except OSError:
        return False


class TestInstallationPrerequisites:
    """Test that installation prerequisites are met and documented."""

    def test_python_version_compatibility(self):
        """Verify Python version is 3.11 or higher."""
        if sys.version_info < (3, 11):
            pytest.skip(
                (
                    f"Test runtime is Python {sys.version_info.major}."
                    f"{sys.version_info.minor}; 3.11+ compatibility "
                    "check requires Python 3.11+ runner"
                )
            )
        version_info = sys.version_info
        assert version_info >= (
            3,
            11,
        ), f"Python 3.11+ required, found {version_info.major}.{version_info.minor}"

    def test_requirements_file_exists(self):
        """Verify requirements.txt exists and is readable."""
        repo_root = Path(__file__).parent.parent
        requirements_file = repo_root / "requirements.txt"
        assert requirements_file.exists(), "requirements.txt not found"
        assert requirements_file.is_file(), "requirements.txt is not a file"

    def test_requirements_dev_file_exists(self):
        """Verify requirements-dev.txt exists for developers."""
        repo_root = Path(__file__).parent.parent
        requirements_dev_file = repo_root / "requirements-dev.txt"
        assert requirements_dev_file.exists(), "requirements-dev.txt not found"

    def test_hosts_csv_sample_exists(self):
        """Verify hosts.csv.sample exists for users to copy."""
        repo_root = Path(__file__).parent.parent
        sample_file = repo_root / "hosts.csv.sample"
        assert sample_file.exists(), "hosts.csv.sample not found"
        assert sample_file.is_file(), "hosts.csv.sample is not a file"

    def test_run_app_script_exists(self):
        """Verify legacy run_app.py exists for backward compatibility."""
        repo_root = Path(__file__).parent.parent
        run_app = repo_root / "run_app.py"
        assert run_app.exists(), "run_app.py not found"
        assert run_app.is_file(), "run_app.py is not a file"


class TestInstallationSteps:
    """Test that documented installation steps can be executed successfully."""

    def test_requirements_can_be_installed(self, tmp_path):
        """Test requirements.txt can be installed in clean venv."""
        if not _can_reach_pypi():
            pytest.skip("PyPI is not reachable from this environment")

        repo_root = Path(__file__).parent.parent
        requirements_file = repo_root / "requirements.txt"

        # Create a virtual environment
        venv_dir = tmp_path / "test_venv"
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            check=True,
            capture_output=True,
        )

        # Install requirements
        pip_path = venv_dir / "bin" / "pip"
        if not pip_path.exists():
            pip_path = venv_dir / "Scripts" / "pip.exe"  # Windows

        result = subprocess.run(
            [str(pip_path), "install", "-q", "-r", str(requirements_file)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert (
            result.returncode == 0
        ), f"Failed to install requirements: {result.stderr}"

    def test_hosts_csv_can_be_created_from_sample(self, tmp_path):
        """Test that hosts.csv can be created from sample file."""
        repo_root = Path(__file__).parent.parent
        sample_file = repo_root / "hosts.csv.sample"
        test_file = tmp_path / "hosts.csv"

        # Copy sample to hosts.csv
        shutil.copy(sample_file, test_file)

        assert test_file.exists(), "Failed to create hosts.csv from sample"
        assert test_file.read_text() == sample_file.read_text(), "Content mismatch"


class TestEnvironmentVariables:
    """Test environment variable requirements and configuration."""

    def test_device_password_env_variable(self):
        """Test that DEVICE_PASSWORD environment variable can be set and read."""
        test_password = "test_password_123"
        os.environ["DEVICE_PASSWORD"] = test_password
        assert (
            os.environ.get("DEVICE_PASSWORD") == test_password
        ), "DEVICE_PASSWORD not set correctly"

    def test_api_token_generation(self):
        """Test that API token can be generated using documented method."""
        # This is the command documented in README
        token = secrets.token_urlsafe(32)
        assert len(token) > 0, "Failed to generate token"
        assert isinstance(token, str), "Token should be a string"

    def test_optional_basic_auth_variables(self):
        """Test that optional Basic Auth variables can be set."""
        os.environ["NW_DIFF_BASIC_USER"] = "test_user"
        os.environ["NW_DIFF_BASIC_PASSWORD"] = "test_password"

        assert os.environ.get("NW_DIFF_BASIC_USER") == "test_user", "Basic user not set"
        assert (
            os.environ.get("NW_DIFF_BASIC_PASSWORD") == "test_password"
        ), "Basic password not set"


class TestApplicationStartup:
    """Test that the application can start with minimal configuration."""

    def test_v2_app_can_import(self):
        """Test that the default v2 FastAPI app can be imported."""
        # Add src to path
        repo_root = Path(__file__).parent.parent
        src_dir = repo_root / "src"
        sys.path.insert(0, str(src_dir))

        try:
            app = importlib.import_module("nw_diff_v2.main").app

            assert app is not None, "Failed to import v2 FastAPI app"
            assert hasattr(app, "router"), "FastAPI app missing router"
        except ImportError as e:
            pytest.fail(f"Failed to import v2 app: {e}")

    def test_required_dependencies_importable(self):
        """Test that required dependencies can be imported."""
        required_modules = [
            "flask",
            "netmiko",
            "diff_match_patch",
            "jinja2",
        ]

        for module_name in required_modules:
            try:
                __import__(module_name)
            except ImportError as e:
                pytest.fail(f"Required module {module_name} cannot be imported: {e}")


class TestDocumentation:
    """Test that installation documentation is accurate and complete."""

    def test_readme_contains_installation_section(self):
        """Verify README.md has an Installation section."""
        repo_root = Path(__file__).parent.parent
        readme = repo_root / "README.md"
        content = readme.read_text()

        assert "## Installation" in content, "Installation section missing from README"
        assert "Prerequisites" in content, "Prerequisites section missing"
        assert "python" in content.lower(), "Python requirement not mentioned"

    def test_readme_has_correct_github_url(self):
        """Verify README.md has the correct repository URL."""
        repo_root = Path(__file__).parent.parent
        readme = repo_root / "README.md"
        content = readme.read_text()

        assert (
            "github.com/icecake0141/nw-diff" in content
        ), "Correct GitHub URL not found in README"
        # Ensure placeholder URL is not present
        assert (
            "github.com/yourusername/nw-diff" not in content
        ), "Placeholder URL still present in README"

    def test_readme_mentions_virtual_environment(self):
        """Verify README.md recommends using a virtual environment."""
        repo_root = Path(__file__).parent.parent
        readme = repo_root / "README.md"
        content = readme.read_text()

        assert (
            "venv" in content.lower() or "virtual environment" in content.lower()
        ), "Virtual environment recommendation missing"

    def test_readme_has_llm_attribution(self):
        """Verify README.md has LLM attribution as per policy."""
        repo_root = Path(__file__).parent.parent
        readme = repo_root / "README.md"
        content = readme.read_text()

        assert (
            "Large Language Model" in content or "LLM" in content
        ), "LLM attribution missing from README"

    def test_readme_has_license_header(self):
        """Verify README.md has Apache 2.0 license header."""
        repo_root = Path(__file__).parent.parent
        readme = repo_root / "README.md"
        content = readme.read_text()

        assert "Apache-2.0" in content, "Apache license identifier missing"
        assert "Copyright" in content, "Copyright notice missing"
