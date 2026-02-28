# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Docker-based deployment support with production-ready Dockerfile
- Docker Compose configuration for orchestrating application and reverse proxy
- HTTPS/TLS termination via nginx reverse proxy
- Basic Authentication support at the reverse proxy level
- Helper script (`scripts/mk-certs.sh`) for generating self-signed TLS certificates
- Helper script (`scripts/mk-htpasswd.sh`) for managing Basic Auth credentials
- Comprehensive Docker deployment documentation in README.md
- Integration tests for Docker deployment and configuration validation
- Environment variable configuration via `.env.example`
- Persistent Docker volumes for logs, configurations, and diffs
- Security headers and rate limiting in nginx configuration
- Health check endpoints for container orchestration
- Multi-stage Docker build for optimized image size
- Non-root user execution in Docker container for enhanced security
- `scripts/report-local-diff.sh` to inventory mixed worktree changes before commit split
- `scripts/run-v2-ci-postchecks.sh` shared CI post-check bundle for readiness/locks/cutover/summary
- v2 contract summary tool tests for missing/malformed artifact inputs

### Changed
- Updated `.gitignore` to exclude Docker-generated files (certificates, htpasswd)
- Updated `.gitignore` to ignore `.pylint_cache/`
- Hardened `scripts/check-v2-contract.sh` to send auth headers for protected v2 endpoints
- Hardened `scripts/summarize-v2-contract.sh` to tolerate malformed JSON artifacts
- Refactored v2 auth parser to reduce lint suppressions while preserving behavior
- Documented v2 auth and CI fallback behavior in runbook
- Deduplicated duplicated CI post-check logic in both `ci.yml` and `integration.yml`

### Security
- Enforced HTTPS by default with HTTP to HTTPS redirection
- Added configurable Basic Authentication for all endpoints
- Implemented security headers (X-Frame-Options, X-Content-Type-Options, X-XSS-Protection)
- Added rate limiting for general and API endpoints
- Non-root user execution in Docker containers
- Secure credential management via environment variables and external files
