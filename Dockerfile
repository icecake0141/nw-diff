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

# Multi-stage build for production-ready nw-diff deployment
FROM python:3.11-slim AS builder

# Set working directory
WORKDIR /app

# Install build dependencies and CA certificates for SSL
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && update-ca-certificates

# Copy requirements first for better caching
COPY requirements.txt requirements-v2.txt ./

# Install Python packages
# Note: In CI environments with SSL interception, you may need to build with:
# docker build --build-arg SKIP_PIP_SSL_VERIFY=1 ...
ARG SKIP_PIP_SSL_VERIFY=""
RUN if [ -n "$SKIP_PIP_SSL_VERIFY" ]; then \
        pip install --no-cache-dir --user \
            --trusted-host pypi.org \
            --trusted-host files.pythonhosted.org \
            --trusted-host pypi.python.org \
            -r requirements.txt -r requirements-v2.txt; \
    else \
        pip install --no-cache-dir --user -r requirements.txt -r requirements-v2.txt; \
    fi

# Production stage
FROM python:3.11-slim

# Create non-root user for security
RUN useradd -m -u 1000 -s /bin/bash nwdiff

# Set working directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /root/.local /home/nwdiff/.local

# Copy application code
COPY --chown=nwdiff:nwdiff src/ ./src/
COPY --chown=nwdiff:nwdiff templates/ ./templates/
COPY --chown=nwdiff:nwdiff hosts.csv.sample ./hosts.csv.sample

# Create necessary directories with correct permissions.
# Pre-creating v2 runtime paths lets Docker initialize named volumes
# with writable ownership for the non-root runtime user.
RUN mkdir -p logs dest origin diff backup data artifacts_v2 && \
    chown -R nwdiff:nwdiff logs dest origin diff backup data artifacts_v2

# Switch to non-root user
USER nwdiff

# Add user's local bin to PATH
ENV PATH=/home/nwdiff/.local/bin:$PATH
ENV PYTHONPATH=/app/src

# Expose application port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/v2').read()" || exit 1

# Run the application
CMD ["uvicorn", "nw_diff_v2.main:app", "--host", "0.0.0.0", "--port", "5000", "--app-dir", "src"]
