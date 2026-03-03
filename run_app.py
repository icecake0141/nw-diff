#!/usr/bin/env python3
"""
Copyright 2025 NW-Diff Contributors
SPDX-License-Identifier: Apache-2.0

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

This file was created or modified with the assistance of an AI (Large Language Model).
Review required for correctness, security, and licensing.

Legacy v1 (Flask) wrapper script.
Preferred runtime is v2 (FastAPI): `uvicorn nw_diff_v2.main:app --app-dir src`.
"""

import os
import sys
from pathlib import Path

# Add src directory to path so nw_diff module can be imported
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

# Import the legacy Flask app (v1)
from nw_diff.app import app  # pylint: disable=wrong-import-position,import-error

if __name__ == "__main__":
    # Import logger after module is loaded
    from nw_diff.logging_config import logger  # pylint: disable=import-outside-toplevel

    # Read debug mode from environment variable, default to False for security
    debug_mode = os.environ.get("APP_DEBUG", "").lower() == "true"

    # Read host and port from environment variables
    # Default to 127.0.0.1 for dev/single-user safety
    # Set FLASK_RUN_HOST=0.0.0.0 in container environments for network accessibility
    host = os.environ.get("FLASK_RUN_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_RUN_PORT", "5000"))

    logger.warning(
        "run_app.py starts legacy v1 Flask runtime. Prefer v2: "
        "uvicorn nw_diff_v2.main:app --host %s --port %d --app-dir src",
        host,
        port,
    )
    logger.info("Starting legacy Flask app on %s:%d (debug=%s)", host, port, debug_mode)
    app.run(host=host, port=port, debug=debug_mode)
