<!--
Copyright 2025 NW-Diff Contributors
SPDX-License-Identifier: Apache-2.0

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

This file was created or modified with the assistance of an AI (Large Language Model).
Review required for correctness, security, and licensing.
-->

# NW-Diff Project

[![CI](https://github.com/icecake0141/nw-diff/workflows/CI/badge.svg)](https://github.com/icecake0141/nw-diff/actions/workflows/ci.yml)
[![Integration Tests](https://github.com/icecake0141/nw-diff/workflows/Integration%20Tests/badge.svg)](https://github.com/icecake0141/nw-diff/actions/workflows/integration.yml)

NW-Diff is a network configuration/status capture and diff tool for network devices.
It now includes both:
- a legacy Flask-based v1 implementation (`src/nw_diff`)
- a FastAPI-based v2 implementation (`src/nw_diff_v2`)

As of March 2, 2026, the repository default container runtime is v2.

## Current Default Runtime (v2)

- `docker-compose.yml` starts v2 API/UI with `uvicorn nw_diff_v2.main:app`.
- `docker/nginx.conf` proxies:
  - `/api/v2/*` to v2 API
  - `/v2` to v2 UI
  - `/` redirects to `/v2`
- Core health checks:
  - `GET /health` (nginx liveness)
  - `GET /api/v2/system/health`
  - `GET /api/v2/system/readiness`

Legacy v1 (`/api/*`, `/capture/*`, `/logs`, `/export/*`) sections below are retained as reference and are not the default docker route.

## Table of Contents

- [Features](#features)
- [Customizing Network Device Commands](#customizing-network-device-commands)
- [Installation](#installation)
- [Usage](#usage)
- [Docker Deployment](#docker-deployment)
- [Development](#development)
- [Japanese Translation](#japanese-translation)

## Features

- **Device Configuration:**
  Device details (hostname, IP address, SSH port, username, and device model) are maintained in a CSV file (`hosts.csv`).

- **Data Capture:**
  Two endpoints capture data from each device:
  - `/capture/origin/<hostname>`: Captures the initial (or original) data.
  - `/capture/dest/<hostname>`: Captures the latest (or destination) data.

  The captured outputs are stored in the `origin` and `dest` directories, respectively.

  **Timeout Handling:**
  - Each command has a 10-second timeout to prevent hanging on unresponsive devices
  - If a command times out, it is logged as an error and skipped
  - The session continues with remaining commands instead of aborting
  - Timeout errors are logged with the specific device and command for troubleshooting
  - This ensures maximum data collection even in unreliable network conditions

- **Real-Time Session Log Streaming:**
  Stream Netmiko session logs to the WebUI using a per-task log file and SSE:
  - Start a streaming task with `POST /api/capture/<base>/<hostname>/stream`
    (or `POST /api/capture_all/<base>/stream` for batch capture)
  - Connect to `GET /api/tasks/<task_id>/stream` (Server-Sent Events) for live output
  - Cancel tasks with `POST /api/tasks/<task_id>/cancel`
  - Task logs default to `logs/tasks/<task_id>.log` (override with
    `NW_DIFF_TASK_LOG_DIR`)
  - Logs are rotated by count (`NW_DIFF_TASK_LOG_MAX_FILES`, default 200) and
    retained for `NW_DIFF_TASK_LOG_RETENTION_SECONDS` (default 3600)
  - `DEVICE_PASSWORD` and `password=...` strings are masked before streaming

- **Configuration Backup:**
  Automatic backup creation before overwriting files to preserve historical configurations and prevent data loss:
  - Backups are created automatically before any file is overwritten during capture operations
  - The rotation system keeps the last 10 backups per file
  - Backups are stored in the `backup/` directory with timestamps
  - Filename format: `YYYYMMDD_HHMMSS_hostname-command.txt`
  - Provides protection against accidental overwrites and enables historical configuration tracking
  - Allows recovery of older configurations if needed

- **Difference Computation:**
  The application compares corresponding files from the `origin` and `dest` directories using diff-match-patch:
  - **Inline View:** Presents the standard diff output.
  - **Side-by-Side View:** Displays the origin data on the left and the computed differences on the right.

  Diff results are converted into HTML files and saved in the `diff` directory.

- **Detailed Device View:**
  Access detailed information for each device through the `/host/<hostname>` endpoint.

## Customizing Network Device Commands

NW-Diff allows you to customize the commands executed on network devices to capture configuration and status data. This section explains how to modify or extend the command set for different device models.

### Command Configuration File

Commands executed on network devices are defined in `src/nw_diff/devices.py`. This file contains:

1. **`DEVICE_COMMANDS`** - A dictionary mapping device models to their command sets
2. **`DEFAULT_COMMANDS`** - Fallback commands used when a device model is not recognized

### Understanding the Command Structure

The `DEVICE_COMMANDS` dictionary uses the following structure:

```python
DEVICE_COMMANDS = {
    "fortinet": (
        "get system status",
        "diag switch physical-ports summary",
        "diag switch trunk summary",
        "diag switch trunk list",
        "diag stp vlan list",
    ),
    "cisco": (
        "show version",
        "show running-config",
    ),
    "junos": (
        "show chassis hardware",
        "show route",
    ),
}
```

- **Key**: Device model name (lowercase string matching the `model` column in `hosts.csv`)
- **Value**: Tuple of command strings to execute on devices of that model

### How to Modify Commands

#### Adding Commands to an Existing Device Model

To add a command to an existing device model, edit the corresponding tuple in `DEVICE_COMMANDS`:

```python
# Before
"cisco": (
    "show version",
    "show running-config",
),

# After - Added "show interfaces status"
"cisco": (
    "show version",
    "show running-config",
    "show interfaces status",
),
```

**Important**: Keep the trailing comma after the last command for Python tuple syntax.

#### Adding a New Device Model

To support a new device model, add a new entry to the `DEVICE_COMMANDS` dictionary:

```python
DEVICE_COMMANDS = {
    # ... existing models ...
    "arista": (
        "show version",
        "show running-config",
        "show interfaces status",
    ),
}
```

Then, ensure the `model` column in your `hosts.csv` matches the new key (e.g., `arista`).

#### Modifying Default Commands

If you want to change the fallback commands used for unrecognized device models, edit the `DEFAULT_COMMANDS` tuple:

```python
# Before
DEFAULT_COMMANDS = ("show version",)

# After
DEFAULT_COMMANDS = (
    "show version",
    "show system information",
)
```

### Best Practices and Safety Guidelines

1. **Test Commands Manually First**
   - Before adding commands to `devices.py`, test them manually on a device to ensure they work correctly and don't cause disruptions
   - Verify that commands are **read-only** and do not modify device configuration

2. **Use Read-Only Commands**
   - Only use commands that retrieve information (e.g., `show`, `get`, `display`)
   - **Never** use configuration commands (e.g., `config`, `set`, `configure`) that could modify device settings
   - Avoid commands that could impact device performance (e.g., `debug` commands in production)

3. **Consider Command Output Size**
   - Be aware that commands producing very large outputs may consume significant storage and memory
   - Test command outputs to ensure they are manageable
   - Consider using filters or specific queries to limit output size when appropriate

4. **Follow Device Vendor Conventions**
   - Use the correct command syntax for each device vendor
   - Consult vendor documentation for proper command usage
   - Be aware of privilege level requirements for commands

5. **Maintain Consistent Formatting**
   - Use tuples (not lists) for command collections
   - Include trailing commas for single-item tuples: `("command",)`
   - Use lowercase for device model keys to match `hosts.csv` entries

6. **Document Your Changes**
   - Add comments explaining why specific commands were added or modified
   - Keep a record of which commands are critical for compliance or monitoring purposes

7. **Backup Before Modifying**
   - Always keep a backup of `devices.py` before making changes
   - Test changes in a development environment before deploying to production

### Example: Complete Modification

Here's a complete example of adding a new device model and modifying an existing one:

```python
# In src/nw_diff/devices.py

DEVICE_COMMANDS = {
    "fortinet": (
        "get system status",
        "diag switch physical-ports summary",
        "diag switch trunk summary",
        "diag switch trunk list",
        "diag stp vlan list",
        # Added for monitoring uplink status
        "get system interface physical",
    ),
    "cisco": (
        "show version",
        "show running-config",
    ),
    "junos": (
        "show chassis hardware",
        "show route",
    ),
    # New device model added
    "arista": (
        "show version",
        "show running-config",
        "show interfaces status",
        "show lldp neighbors",
    ),
}

DEFAULT_COMMANDS = ("show version",)
```

### Verifying Your Changes

After modifying `devices.py`:

1. **Syntax Check**: Run Python syntax validation
   ```bash
   python -m py_compile src/nw_diff/devices.py
   ```

2. **Linting**: Check code quality
   ```bash
   pylint src/nw_diff/devices.py
   ```

3. **Test Capture**: Verify that the application can execute the new commands
   - Start the application
   - Use the `/capture/origin/<hostname>` or `/capture/dest/<hostname>` endpoint for a device using the modified model
   - Check the output files in the `origin` or `dest` directories
   - Review logs for any errors

4. **Restart Application**: Changes to `devices.py` require an application restart to take effect
   ```bash
   # If running locally
   # Stop the current process (Ctrl+C) and restart
   uvicorn nw_diff_v2.main:app --host 127.0.0.1 --port 5000 --app-dir src

   # If running with Docker
   docker compose restart
   ```

### Troubleshooting

**Commands not executing:**
- Verify the device model in `hosts.csv` matches the key in `DEVICE_COMMANDS` (comparison is case-insensitive)
- Check application logs for connection errors or command failures
- Ensure device credentials are correct in environment variables

**Syntax errors:**
- Verify tuple syntax (trailing commas, proper parentheses)
- Ensure all strings are properly quoted
- Run `python -m py_compile src/nw_diff/devices.py` to check for syntax errors

**Permission errors on device:**
- Verify that the user account has sufficient privileges to execute the commands
- Some commands may require enable mode or specific user roles

## Installation

This section covers the basic installation process for end users who want to run NW-Diff. For development setup including linting, testing, and code quality tools, see the [Development](#development) section.

### Prerequisites

- **Python 3.11 or higher** (tested with Python 3.11)
- **pip** (Python package installer)
- **Git** (for cloning the repository)
- Network access to target devices via SSH

### Installation Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/icecake0141/nw-diff.git
   cd nw-diff
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt -r requirements-v2.txt
   ```
   This installs both legacy v1 and default v2 runtime dependencies.

4. **Create the device inventory file:**
   ```bash
   cp hosts.csv.sample hosts.csv
   ```
   Edit `hosts.csv` to add your network devices (hostname, IP address, SSH port, username, device model).

5. **Configure required environment variables:**
   ```bash
   # Required: Password for SSH connections to devices
   export DEVICE_PASSWORD=your_device_password

   # Required for security: Token to protect sensitive API endpoints
   export NW_DIFF_API_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
   ```

   **Important:** The `NW_DIFF_API_TOKEN` protects capture, logs, and export endpoints. Without it, these endpoints will be accessible without authentication.

6. **(Optional) Configure HTTP Basic Authentication:**

   For browser-based access to protected endpoints, set a username and password:
   ```bash
   export NW_DIFF_BASIC_USER=admin
   export NW_DIFF_BASIC_PASSWORD=your_secure_password
   ```

   **Note:** Both Bearer token and Basic Authentication are accepted for protected endpoints when `NW_DIFF_API_TOKEN` is set.

7. **(Optional) Set custom hosts file location:**
   ```bash
   export HOSTS_CSV=/path/to/hosts.csv
   ```
   By default, the application looks for `hosts.csv` in the current directory.

8. **Run the application:**
   ```bash
   export NW_DIFF_ENV=development
   uvicorn nw_diff_v2.main:app --host 127.0.0.1 --port 5000 --app-dir src
   ```
   The v2 UI/API will start on `http://127.0.0.1:5000`.

9. **Access the application:**
   Open your web browser and navigate to [http://localhost:5000/v2](http://localhost:5000/v2)

### Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `DEVICE_PASSWORD` | Yes | Password for SSH connections to network devices |
| `NW_DIFF_API_TOKEN` | Recommended | Secure token for protecting sensitive API endpoints (capture, logs, export) |
| `NW_DIFF_BASIC_USER` | Optional | Username for HTTP Basic Authentication |
| `NW_DIFF_BASIC_PASSWORD` | Optional | Password for HTTP Basic Authentication |
| `NW_DIFF_ENV` | Recommended | Runtime environment (`development`, `production`, etc.) |
| `HOSTS_CSV` | Optional | Custom path to hosts inventory file (default: `hosts.csv`) |
| `DB_URL` | Optional | v2 SQLite DB URL (default: `sqlite:///./nw_diff_v2.db`) |
| `ARTIFACT_ROOT` | Optional | v2 artifact output directory (default: `./artifacts_v2`) |
| `TASK_WORKER_ENABLED` | Optional | Enable in-process queue worker (default: `true`) |
| `TASK_WORKER_THREADS` | Optional | Number of worker threads (default: `1`) |

## Usage

### Running Modes Overview

The application supports two primary running modes:

1. **Local Development Mode**: Start v2 directly via uvicorn on `127.0.0.1:5000`.
2. **Container/Production Mode**: Start via `docker compose`, with nginx reverse proxy and v2 routed under `/api/v2/*` and `/v2`.

v2 FastAPI runtime honors reverse-proxy headers and is designed for nginx fronting in containerized deployment.

### Running in Production Mode (Default)

For default local runtime:

1. **Run the Application:**
   ```bash
   export DEVICE_PASSWORD=your_device_password
   export NW_DIFF_API_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
   export NW_DIFF_ENV=development
   uvicorn nw_diff_v2.main:app --host 127.0.0.1 --port 5000 --app-dir src
   ```
2. **Access the Application:**
   Open your browser and navigate to [http://localhost:5000/v2](http://localhost:5000/v2).

### Running in Development Mode

For containerized runtime (repository default):

1. **Prepare environment file and credentials:**
   ```bash
   cp .env.example .env
   # edit .env and set DEVICE_PASSWORD, NW_DIFF_API_TOKEN
   ./docker/nginx/init-certs-and-htpasswd.sh
   ```
2. **Start stack:**
   ```bash
   docker compose up -d --build
   ```
3. **Access application and health endpoints:**
   - `https://localhost/v2`
   - `https://localhost/api/v2/system/health`
   - `https://localhost/api/v2/system/readiness`

### Interacting with Endpoints

#### Public Endpoints (No Authentication Required)
- **View v2 UI:** `/v2`
- **View host details:** `/v2/hosts/<hostname>`
- **View logs page:** `/v2/logs`

#### Protected Endpoints (Require Authentication)
The v2 API requires auth in production-like environments.
- **Capture/task flow:**
  - `POST /api/v2/captures`
  - `GET /api/v2/tasks/{task_id}`
  - `POST /api/v2/tasks/{task_id}/cancel`
  - `POST /api/v2/tasks/{task_id}/retry`
- **System endpoints:**
  - `GET /api/v2/system/health`
  - `GET /api/v2/system/readiness`
  - `GET /api/v2/system/locks`

**Example using curl with Bearer token:**
```bash
curl -H "Authorization: Bearer your_token_here" http://localhost:5000/api/v2/system/health
```

## Docker Deployment

NW-Diff supports containerized deployment with HTTPS (TLS termination) and optional Basic Authentication via Docker and docker-compose. This provides a secure, production-ready deployment option.

**Architecture Overview:**
- **nginx**: Acts as a reverse proxy with TLS termination, sets `X-Forwarded-*` headers
- **v2 app**: Runs as `uvicorn nw_diff_v2.main:app`
- **Container binding**: v2 app binds to `0.0.0.0:5000` inside the container
- **Network isolation**: Only nginx is exposed to the host; v2 app is accessible only within the Docker network

### Prerequisites

- Docker and Docker Compose installed
- OpenSSL (for generating self-signed certificates)
- Apache Utils (for generating htpasswd file) - `apt-get install apache2-utils` or `yum install httpd-tools`

### Quick Start

1. **Clone the repository and navigate to project directory:**
   ```bash
   git clone https://github.com/icecake0141/nw-diff.git
   cd nw-diff
   ```

2. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env and set DEVICE_PASSWORD and NW_DIFF_API_TOKEN
   ```

3. **Generate TLS certificates and Basic Auth (automated):**

   **Option A: Automated Setup (Recommended for CI/CD)**
   ```bash
   # Set environment variables
   export NW_DIFF_BASIC_USER=admin
   export NW_DIFF_BASIC_PASSWORD=your_strong_password
   export CERT_HOSTNAME=myserver.example.com  # Optional, defaults to localhost

   # Run automated initialization script
   ./docker/nginx/init-certs-and-htpasswd.sh
   ```
   This script will:
   - Generate self-signed TLS certificates (for development/demo)
   - Create .htpasswd file with provided credentials
   - Validate file permissions and configuration
   - Display security warnings and reminders

   **Option B: Interactive Setup**
   ```bash
   # Generate certificates interactively
   ./scripts/mk-certs.sh
   # Follow prompts to generate certificates
   # Or specify hostname: CERT_HOSTNAME=myserver.example.com ./scripts/docker-setup.sh

   # Generate Basic Auth credentials interactively
   ./scripts/mk-htpasswd.sh
   # Follow prompts to create username/password
   ```

4. **Create hosts.csv inventory file:**
   ```bash
   cp hosts.csv.sample hosts.csv
   # Edit hosts.csv with your device information
   ```

5. **Start the application stack:**
   ```bash
   docker compose up -d --build
   ```

6. **Access the application:**
   - HTTPS UI: `https://localhost/v2` (accept self-signed certificate warning in dev)
   - API health: `https://localhost/api/v2/system/health`
   - You'll be prompted for Basic Auth credentials

7. **View logs:**
   ```bash
   docker compose logs -f
   ```

8. **Stop the application:**
   ```bash
   docker compose down
   ```

### Configuration

#### Environment Variables

Set these in your `.env` file:

- `DEVICE_PASSWORD`: Password for SSH connections to network devices
- `NW_DIFF_API_TOKEN`: Secure token for API authentication (generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`)
- `NW_DIFF_BASIC_USER`: (Optional) Username for HTTP Basic Authentication
- `NW_DIFF_BASIC_PASSWORD_HASH`: (Optional) Hashed password for Basic Authentication (generate with `python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('password'))"`)
- `NW_DIFF_BASIC_PASSWORD`: (Optional) Plain password for Basic Authentication (development only - use hashed password in production)
- `NW_DIFF_ENV`: Runtime mode (`development`, `production`, etc.)
- `HOSTS_CSV`: Optional custom path to hosts inventory file
- `DB_URL`: Optional SQLite path for v2 task/lock DB
- `ARTIFACT_ROOT`: Optional artifact output path for v2

**Authentication Modes:**
- If `NW_DIFF_API_TOKEN` is not set: No authentication required (legacy mode)
- If `NW_DIFF_API_TOKEN` is set:
  - API clients can use Bearer token: `Authorization: Bearer <token>`
  - Browser users can use Basic auth: `Authorization: Basic <base64(user:pass)>`
  - Both methods are accepted for protected v2 endpoints under `/api/v2/*`

#### TLS/SSL Certificates

For **development/testing**, use the provided script to generate self-signed certificates:
```bash
./scripts/mk-certs.sh
```

For **production**, you should:
- Use certificates from a trusted Certificate Authority (CA), or
- Use Let's Encrypt with Caddy or certbot, or
- Mount your existing certificates:
  ```bash
  # Place your certificates in docker/certs/
  cp /path/to/your/cert.pem docker/certs/cert.pem
  cp /path/to/your/key.pem docker/certs/key.pem
  chmod 644 docker/certs/cert.pem
  chmod 600 docker/certs/key.pem
  ```

#### Basic Authentication

Basic Authentication is enabled by default for all endpoints. To manage users:

**Add a user:**
```bash
./scripts/mk-htpasswd.sh
```

**Add additional users:**
```bash
htpasswd docker/.htpasswd <username>
```

**Disable Basic Auth (not recommended for production):**
Edit `docker/nginx.conf` and comment out these lines:
```nginx
# auth_basic "NW-Diff Access";
# auth_basic_user_file /etc/nginx/.htpasswd;
```
Then restart: `docker-compose restart nginx`

#### Persistent Data

Docker volumes are used for persistent storage:
- `nw-diff-logs`: Application logs
- `nw-diff-v2-db`: v2 SQLite DB files
- `nw-diff-v2-artifacts`: v2 generated artifacts

To backup or migrate data:
```bash
# Backup volumes
docker run --rm -v nw-diff-logs:/data -v $(pwd):/backup alpine tar czf /backup/nw-diff-logs-backup.tar.gz -C /data .

# Restore volumes
docker run --rm -v nw-diff-logs:/data -v $(pwd):/backup alpine tar xzf /backup/nw-diff-logs-backup.tar.gz -C /data
```

### Security Best Practices

#### Overview
NW-Diff is designed with security as a priority, but proper deployment requires careful configuration. This section outlines critical security measures for production deployments.

#### TLS/SSL Certificates

**Development/Demo Environments:**
- Use the provided self-signed certificate generation:
  ```bash
  ./scripts/mk-certs.sh
  # or for automated setup
  ./docker/nginx/init-certs-and-htpasswd.sh
  ```
- Accept browser security warnings (expected for self-signed certificates)
- **NEVER** use self-signed certificates in production

**Production Environments:**
- **Recommended**: Let's Encrypt (free, automated, widely trusted)
  - Use certbot or similar tools for automated renewal
  - Example with certbot:
    ```bash
    certbot certonly --standalone -d yourdomain.com
    cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem docker/certs/cert.pem
    cp /etc/letsencrypt/live/yourdomain.com/privkey.pem docker/certs/key.pem
    ```
- **Alternative**: Commercial CA (DigiCert, Sectigo, GlobalSign, etc.)
- **Enterprise**: Internal PKI/CA infrastructure
- **Important**: After installing trusted certificates, enable HSTS in `docker/nginx.conf`:
  ```nginx
  add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
  ```
- **WARNING**: Do NOT enable HSTS with self-signed certificates - it will cause persistent browser issues

#### Authentication and Authorization

**API Token Security:**
1. Generate a strong, random token:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
2. Store in environment variables or secrets manager (never in code)
3. Use different tokens for dev/staging/production
4. Rotate tokens regularly (every 90 days recommended)
5. Never commit `.env` files containing tokens

**Basic Authentication:**
1. Use strong passwords (minimum 12 characters, mixed case, numbers, symbols)
2. Generate hashed passwords:
   ```bash
   ./scripts/mk-htpasswd.sh
   # or for automated deployments
   export NW_DIFF_BASIC_USER=admin
   export NW_DIFF_BASIC_PASSWORD=your_strong_password
   ./docker/nginx/init-certs-and-htpasswd.sh
   ```
3. **Never** commit `docker/.htpasswd` to version control (covered by `.gitignore`)
4. Implement account lockout policies if possible (via nginx modules or WAF)

**Device Credentials:**
1. Store `DEVICE_PASSWORD` securely (secrets manager, encrypted vault)
2. Use read-only accounts on network devices where possible
3. Implement SSH key authentication instead of passwords when supported
4. Rotate device credentials regularly

#### Network Security

1. **Firewall Configuration:**
   - Restrict HTTPS (443) access to authorized networks/IPs
   - Close HTTP (80) port if not needed (optional, redirects to HTTPS by default)
   - Use VPN or bastion host for remote access

2. **Reverse Proxy Hardening:**
   - The nginx configuration includes rate limiting by default
   - Adjust rate limits in `docker/nginx.conf` based on your usage patterns:
     ```nginx
     limit_req_zone $binary_remote_addr zone=general:10m rate=10r/s;
     limit_req_zone $binary_remote_addr zone=api:10m rate=5r/s;
     ```
   - Consider adding WAF (Web Application Firewall) for additional protection

3. **Container Security:**
   - Run containers as non-root users where possible
   - Use Docker secrets for sensitive data instead of environment variables
   - Regularly scan container images for vulnerabilities:
     ```bash
     docker scan nw-diff:latest
     ```

#### Data Protection

1. **Sensitive File Handling:**
   - Verify `.gitignore` excludes: `docker/.htpasswd`, `docker/certs/`, `.env`, `hosts.csv`
   - Store device inventory (`hosts.csv`) outside repository in production
   - Use volume mounts for sensitive data:
     ```bash
     docker run -v /secure/path/hosts.csv:/app/hosts.csv:ro -e HOSTS_CSV=/app/hosts.csv ...
     ```

2. **Secrets Management:**
   - Use environment-specific secrets (development vs. production)
   - Consider using Docker secrets, Kubernetes secrets, or dedicated secrets managers (HashiCorp Vault, AWS Secrets Manager, etc.)
   - Never log or expose secrets in error messages

3. **Configuration Backups:**
   - Encrypt backups of configuration data
   - Store backups in secure, access-controlled locations
   - Implement retention policies for compliance

#### Monitoring and Auditing

1. **Log Management:**
   - Review nginx access/error logs regularly:
     ```bash
     docker-compose logs nginx | grep -E "40[134]|50[0-3]"
     ```
   - Monitor for suspicious activity: repeated 401/403 errors, unusual traffic patterns
   - Consider centralized logging (ELK stack, Splunk, etc.)

2. **Security Auditing:**
   - Run regular security scans:
     ```bash
     pip-audit -r requirements.txt
     docker scan nw-diff:latest
     ```
   - Review and update dependencies quarterly
   - Subscribe to security advisories for Flask, nginx, and dependencies

3. **Access Monitoring:**
   - Log all capture operations and configuration changes
   - Implement alerting for unauthorized access attempts
   - Regular access reviews (who has credentials, tokens, etc.)

#### Regular Maintenance

1. **Updates:**
   - Keep base Docker images updated: `docker-compose pull`
   - Update Python dependencies: `pip install -r requirements.txt --upgrade`
   - Monitor for security advisories and CVEs

2. **Certificate Renewal:**
   - Let's Encrypt certificates expire every 90 days - automate renewal
   - Set calendar reminders for manual certificate renewals
   - Test certificate validity regularly:
     ```bash
     openssl x509 -in docker/certs/cert.pem -noout -enddate
     ```

3. **Credential Rotation:**
   - Rotate API tokens every 90 days
   - Update Basic Auth passwords every 180 days
   - Change device passwords according to organizational policy

#### Production Deployment Checklist

Before deploying to production, verify:

- [ ] Using trusted TLS certificates (not self-signed)
- [ ] HSTS header enabled in `docker/nginx.conf`
- [ ] Strong, unique passwords for all authentication
- [ ] API token generated and securely stored
- [ ] `.env` file not committed to version control
- [ ] `hosts.csv` stored outside repository or properly secured
- [ ] Firewall rules configured to restrict access
- [ ] Container images scanned for vulnerabilities
- [ ] Logs are being collected and monitored
- [ ] Backup strategy implemented and tested
- [ ] Debug mode disabled (`APP_DEBUG=false`)
- [ ] Running latest stable versions of all dependencies
- [ ] Incident response plan documented

#### Demo vs. Production Configurations

**Demo/Development Environment:**
- Self-signed certificates acceptable
- HSTS disabled (commented out)
- Basic Auth optional
- Bind to `127.0.0.1` for local testing
- Debug mode can be enabled temporarily
- Less strict rate limiting

**Production Environment:**
- **Must use** trusted TLS certificates
- **Must enable** HSTS header
- **Must use** Basic Auth + API tokens
- Bind to `0.0.0.0` only within containers (nginx proxy)
- Debug mode **must be disabled**
- Strict rate limiting and monitoring
- Regular security audits and updates

#### Reporting Security Issues

If you discover a security vulnerability in NW-Diff:
1. **Do NOT** open a public GitHub issue
2. Email security concerns to repository maintainers privately
3. Include detailed information: steps to reproduce, impact assessment
4. Allow reasonable time for remediation before public disclosure

### Troubleshooting

**Certificate errors in browser:**
- Self-signed certificates will show warnings - this is expected for development
- Add exception in browser or import certificate to system trust store (see scripts/mk-certs.sh output)

**Connection refused:**
- Verify containers are running: `docker-compose ps`
- Check logs: `docker-compose logs`

**Authentication failures:**
- Verify .htpasswd file exists: `ls -la docker/.htpasswd`
- Test credentials: `htpasswd -v docker/.htpasswd <username>`

**Permission errors:**
- Ensure certificate files have correct permissions (cert.pem: 644, key.pem: 600)
- Check volume permissions: `docker-compose exec nw-diff ls -la /app`

**Docker build SSL certificate errors:**
- If building in a corporate/CI environment with SSL interception, use:
  ```bash
  docker build --build-arg SKIP_PIP_SSL_VERIFY=1 -t nw-diff:latest .
  ```
- This adds `--trusted-host` flags for PyPI domains during pip install
- **Note:** Only use this workaround in trusted environments; it bypasses SSL verification

## Development

### Local Development Setup

1. **Install development dependencies:**
   ```bash
   pip install -r requirements.txt -r requirements-dev.txt
   ```

2. **Run security audit:**
   ```bash
   pip-audit -r requirements.txt -r requirements-dev.txt
   ```

3. **Format, lint, type check, and test:**
   ```bash
   black src tests
   pylint src tests
   mypy src tests
   pytest
   ```

4. **Run pre-commit hooks:**
   ```bash
   pre-commit run --all-files
   ```

### Testing

NW-Diff includes comprehensive test coverage to ensure quality and security:

#### Unit and Integration Tests

Run the full test suite locally:
```bash
pytest -v
```

The test suite includes:
- **Unit tests**: Core application logic, authentication, authorization
- **Integration tests**: Docker deployment configuration, security settings
- **Type checking**: Static type analysis with mypy
- **Linting**: Code quality checks with pylint
- **Formatting**: Code style verification with black

#### Full-Stack Integration Tests (CI)

The project includes automated end-to-end tests that validate the complete Docker Compose deployment:

**What is tested:**
- ✅ Docker Compose builds successfully
- ✅ HTTPS (TLS/SSL) is enabled and functioning
- ✅ HTTP correctly redirects to HTTPS
- ✅ Basic Authentication is required and working
- ✅ Bearer token authentication on protected endpoints
- ✅ Invalid credentials are rejected (401 responses)
- ✅ Valid credentials grant access (200 responses)
- ✅ Self-signed certificates are generated correctly
- ✅ All security headers are present
- ✅ Services start healthy and remain stable

**Running integration tests locally:**

1. **Setup and start the stack:**
   ```bash
   # Generate certificates and .htpasswd
   export NW_DIFF_BASIC_USER=admin
   export NW_DIFF_BASIC_PASSWORD=yourpassword
   ./docker/nginx/init-certs-and-htpasswd.sh

   # Create hosts.csv (or copy from sample)
   cp hosts.csv.sample hosts.csv

   # Set environment variables in .env
   cp .env.example .env
   # Edit .env with your values

   # Start the stack
   docker-compose up -d
   ```

2. **Run the integration test script:**
   ```bash
   export NW_DIFF_BASIC_USER=admin
   export NW_DIFF_BASIC_PASSWORD=yourpassword
   export NW_DIFF_API_TOKEN=your_token_here
   ./scripts/test-integration.sh
   ```

3. **Cleanup:**
   ```bash
   docker-compose down -v
   ```

#### Continuous Integration

The project uses GitHub Actions for automated testing on every push and pull request:

- **CI Workflow** (`.github/workflows/ci.yml`): Runs unit tests, linting, type checking, security audits
- **Integration Workflow** (`.github/workflows/integration.yml`): Runs full-stack Docker Compose tests with HTTPS and authentication validation

View test results: [GitHub Actions](https://github.com/icecake0141/nw-diff/actions)

#### Test Coverage

Tests cover:
- Flask application routes and authentication logic
- Docker and nginx configuration validation
- TLS/SSL certificate setup and validation
- Basic Authentication and Bearer token flows
- Security headers and HTTP status codes
- File permissions and .gitignore rules
- SPDX license headers and LLM attribution

#### Writing Tests

When contributing, please:
- Add tests for new features or bug fixes
- Ensure all tests pass locally before submitting PR
- Follow existing test patterns in `tests/` directory
- Include SPDX headers and LLM attribution in test files
- Test both positive and negative cases (success and failure scenarios)

### Pre-commit Hooks

Run pre-commit hooks to ensure code quality:
```bash
pre-commit run --all-files
```

### V2 Reimplementation Scaffold

This repository now includes a parallel scaffold under `src/nw_diff_v2/` to support
a clean-slate reimplementation with FastAPI.

Current scaffold features:
- Minimal web UI: `GET /v2`
  - task inspect / cancel / live stream controls
  - recent task auto refresh with status filter
  - host-name search and running-only toggle for task list
  - recent tasks table with row-level select/cancel/live actions
  - host detail page: `GET /v2/hosts/{hostname}`
  - logs page: `GET /v2/logs`
- Typed settings with environment-based auth policy
- `hosts.csv` row validation (invalid rows are skipped)
- Host-level capture locks (same-host concurrency is rejected)
- Host locks are persisted in SQLite (cross-process safe on shared DB file)
- stale host locks auto-expire via `host_lock_timeout_seconds`
- Background queue worker (DB-backed queued task execution)
- `mode=single` strictly requires exactly one host
- `mode=batch` captures all hosts when `hosts=[]`, or only the provided subset
- Initial API endpoints:
  - `POST /api/v2/captures`
  - `GET /api/v2/tasks/{task_id}`
  - `GET /api/v2/tasks?limit=50&offset=0&status_filter=completed&host_contains=router&running_only=true`
  - `POST /api/v2/tasks/{task_id}/cancel`
  - `POST /api/v2/tasks/{task_id}/retry`
  - `GET /api/v2/tasks/{task_id}/stream?tail_lines=20`
    - supports `Last-Event-ID` resume and heartbeat keepalive
  - `POST /api/v2/compare/files`
  - `GET /api/v2/diff/{hostname}?view=inline|sidebyside`
  - `GET /api/v2/hosts/{hostname}/detail?view=inline|sidebyside&status_filter=changed|identical|unavailable|not_found&command_contains=...`
  - `GET /api/v2/hosts/summary?limit=50&host_contains=router&prioritize_failed=true`
  - `GET /api/v2/logs?source=app|task&limit=1000&contains=...`
  - `GET /api/v2/exports/{hostname}`
  - `GET /api/v2/exports/{hostname}/diff-json`
  - `GET /api/v2/exports/{hostname}/html`
  - `GET /api/v2/system/worker`
  - `GET /api/v2/system/health`
  - `GET /api/v2/system/readiness`
  - `GET /api/v2/system/locks`
  - `POST /api/v2/system/locks/cleanup`
  - `POST /api/v2/system/locks/release`
  - `GET /api/v2/system/routes`
  - `GET /api/v2/system/contract`

Run locally:
```bash
export DEVICE_PASSWORD=example
export NW_DIFF_ENV=development
uvicorn nw_diff_v2.main:app --reload --app-dir src
```

Run standalone worker (optional split deployment):
```bash
export DEVICE_PASSWORD=example
export NW_DIFF_ENV=development
python -m nw_diff_v2.worker
```

Run v2 contract smoke check (local/CI):
```bash
PYTHON_BIN=.venv/bin/python DEVICE_PASSWORD=example NW_DIFF_ENV=development ./scripts/check-v2-contract.sh
```
Run full preflight gate (contract/readiness/locks/cutover/message):
```bash
PYTHON_BIN=.venv/bin/python DEVICE_PASSWORD=example NW_DIFF_ENV=development ./scripts/run-v2-preflight.sh
```
Notes:
- preflight includes deploy template validation and writes `DEPLOY_VALIDATION_FILE` JSON.
- set `DEPLOY_VALIDATION_STRICT=true` to fail on missing `nginx`/`systemd-analyze`.

Optional outputs:
```bash
CONTRACT_OUTPUT=.artifacts/v2_contract.json HEALTH_OUTPUT=.artifacts/v2_health.json READINESS_OUTPUT=.artifacts/v2_readiness.json LOCKS_OUTPUT=.artifacts/v2_locks.json CONTRACT_CURRENT_OUTPUT=.artifacts/v2_contract_current.json DEPLOY_VALIDATION_FILE=.artifacts/deploy_template_validation.json LOG_OUTPUT=.artifacts/v2_contract.log
```

Run readiness checker (non-zero on degraded):
```bash
.venv/bin/python scripts/check-v2-readiness.py --url http://127.0.0.1:18080/api/v2/system/readiness
```
Run lock checker (non-zero on stale/overflow):
```bash
.venv/bin/python scripts/check-v2-locks.py --url http://127.0.0.1:18080/api/v2/system/locks --max-locks 100
```

Evaluate cutover GO/NO-GO:
```bash
.venv/bin/python scripts/evaluate-v2-cutover.py --readiness-file .artifacts/v2_readiness.json --contract-diff-file .artifacts/v2_contract_diff.json --deploy-validation-file .artifacts/deploy_template_validation.json
```
Explicit thresholds example:
```bash
.venv/bin/python scripts/evaluate-v2-cutover.py --readiness-file .artifacts/v2_readiness.json --contract-diff-file .artifacts/v2_contract_diff.json --deploy-validation-file .artifacts/deploy_template_validation.json --max-queued 0 --max-running 5 --max-failed 0 --max-locked 0
```
Render cutover message:
```bash
.venv/bin/python scripts/render-v2-cutover-message.py --input .artifacts/v2_cutover_eval.json --format markdown --output .artifacts/v2_cutover_message.md
```

Cutover threshold env vars:
```bash
V2_CUTOVER_MAX_QUEUED=0
V2_CUTOVER_MAX_RUNNING=5
V2_CUTOVER_MAX_FAILED=0
V2_CUTOVER_MAX_LOCKED=0
```
Examples:
- staging: `docs/env/v2-cutover-staging.env.example`
- production: `docs/env/v2-cutover-production.env.example`

Generate/update contract snapshot file:
```bash
.venv/bin/python scripts/generate-v2-contract.py --output docs/contract/v2.json
```

Diff baseline vs current generated snapshot:
```bash
.venv/bin/python scripts/generate-v2-contract.py --output .artifacts/v2_contract_current.json
.venv/bin/python scripts/diff-v2-contract.py --baseline docs/contract/v2.json --candidate .artifacts/v2_contract_current.json --fail-on-diff
```

Write machine-readable diff JSON:
```bash
.venv/bin/python scripts/diff-v2-contract.py --baseline docs/contract/v2.json --candidate .artifacts/v2_contract_current.json --json-output .artifacts/v2_contract_diff.json
```

CI note:
- `.github/workflows/ci.yml` and `.github/workflows/integration.yml` both run the v2 contract smoke check and upload its artifacts.
- Both workflows also append a contract summary to GitHub Job Summary via `scripts/summarize-v2-contract.sh`.
- Both workflows verify `docs/contract/v2.json` is up to date via `scripts/diff-v2-contract.py`.
- Both workflows evaluate cutover decision via `scripts/evaluate-v2-cutover.py`.
- Operations runbook: `docs/V2_RUNBOOK.md`.
- Cutover checklist: `docs/V2_CUTOVER_CHECKLIST.md`.
- systemd templates: `docs/deploy/nw-diff-v2-api.service.example`, `docs/deploy/nw-diff-v2-worker.service.example`.
- nginx templates: `docs/deploy/nginx-v2.conf.example`, `docs/deploy/nginx-v1-v2-cutover.conf.example`.

Validate deploy templates:
```bash
./scripts/validate-deploy-templates.sh
```
With summary output:
```bash
SUMMARY_PATH=/tmp/deploy_template_summary.md ./scripts/validate-deploy-templates.sh
```
With JSON output:
```bash
JSON_OUTPUT=/tmp/deploy_template_validation.json ./scripts/validate-deploy-templates.sh
```

Notes:
- v2 keeps SQLite-only task persistence (`sqlite:///...`) by design.
- Queue worker controls:
  - `task_worker_enabled` (default: `true`)
  - `task_worker_threads` (default: `1`)
  - `task_worker_poll_seconds` (default: `0.5`)
- Readiness thresholds:
  - `readiness_max_queued` (default: `100`)
  - `readiness_max_running` (default: `20`)
  - `readiness_max_locked` (default: `100`)
- On startup, orphaned `running` tasks are auto-recovered to `failed`.
- If `NW_DIFF_API_TOKEN` is set, Bearer token auth is enforced and Basic auth
  fallback is available via `NW_DIFF_BASIC_USER` + password/hash env vars.
- In v2, omitting `NW_DIFF_API_TOKEN` is allowed only for development-like envs
  (`development`/`dev`/`local`/`test`). Non-development envs fail fast at startup.
- Batch conflict policy is configurable via `batch_conflict_policy`:
  - `all_or_nothing` (default): any lock conflict returns `409`
  - `skip_locked`: start capture for unlocked hosts and report conflicts
- Host lock behavior:
  - Same host cannot run concurrent captures (`409` on conflict)
  - Different hosts can run in parallel
  - Stale locks auto-expire via `host_lock_timeout_seconds`
  - API/worker startup also performs stale lock cleanup
- `hosts.csv` rows are validated before use (safe hostname/user/model chars,
  valid IP, valid port range, and field length limits).
- Task cancel API only accepts `queued`/`running`; completed tasks return `409`.
- Migration notes: see `docs/V2_MIGRATION.md`.
- Current implementation snapshot: `docs/V2_IMPLEMENTATION_STATUS.md`.
- Commit split plan: `docs/V2_COMMIT_SPLIT_PLAN.md`.

## Japanese Translation

Note: The Japanese section below may include legacy v1 examples.
For current v2-first operational instructions, use `docs/README_ja.md`.

# NW-Diff プロジェクト

[![CI](https://github.com/icecake0141/nw-diff/workflows/CI/badge.svg)](https://github.com/icecake0141/nw-diff/actions/workflows/ci.yml)
[![Integration Tests](https://github.com/icecake0141/nw-diff/workflows/Integration%20Tests/badge.svg)](https://github.com/icecake0141/nw-diff/actions/workflows/integration.yml)

NW-Diff は、ネットワークデバイスから収集された設定またはステータスデータを取得、比較、表示するために設計された Flask ベースのウェブアプリケーションです。Netmiko を利用してデバイスに接続し、CSV ファイルに定義されたデータをキャプチャします。diff-match-patch を使用して、2 つのデータセット間の差分を計算し、インライン表示およびサイドバイサイド表示で結果を提示します。差分 HTML ファイルは生成され、専用の "diff" ディレクトリに保存され、後で確認できます。

## 機能

- **デバイス設定:**
  ホスト情報（ホスト名、IP アドレス、SSH ポート、ユーザー名、デバイスモデル）は CSV ファイル (`hosts.csv`) に保持されます。

- **データキャプチャ:**
  2 つのエンドポイントにより各デバイスのデータをキャプチャします:
  - `/capture/origin/<hostname>`: 初期（または元の）データをキャプチャします。
  - `/capture/dest/<hostname>`: 最新（または宛先）のデータをキャプチャします。

  キャプチャされた出力は、それぞれ `origin` と `dest` ディレクトリに保存されます。

- **リアルタイムのセッションログ配信:**
  Netmiko の session_log をタスク単位のログファイルとして保存し、SSE で配信できます:
  - `POST /api/capture/<base>/<hostname>/stream`（バッチは
    `POST /api/capture_all/<base>/stream`）でタスクを開始
  - `GET /api/tasks/<task_id>/stream` に接続してリアルタイム出力を取得
  - `POST /api/tasks/<task_id>/cancel` でタスクをキャンセル
  - ログは既定で `logs/tasks/<task_id>.log` に保存
    (`NW_DIFF_TASK_LOG_DIR` で変更可)
  - `NW_DIFF_TASK_LOG_MAX_FILES`（既定 200）でローテーションし、
    `NW_DIFF_TASK_LOG_RETENTION_SECONDS`（既定 3600）で保持
  - `DEVICE_PASSWORD` や `password=...` の文字列は配信前にマスク

- **設定バックアップ:**
  履歴設定を保持し、データ損失を防ぐため、ファイル上書き前に自動バックアップを作成します:
  - キャプチャ操作時、ファイルが上書きされる前に自動的にバックアップが作成されます
  - ローテーションシステムにより、ファイルごとに最新の10個のバックアップが保持されます
  - バックアップは `backup/` ディレクトリにタイムスタンプ付きで保存されます
  - ファイル名形式: `YYYYMMDD_HHMMSS_hostname-command.txt`
  - 誤った上書きから保護し、履歴設定の追跡を可能にします
  - 必要に応じて古い設定を復元できます

- **差分計算:**
  アプリケーションは、`origin` と `dest` ディレクトリ内の対応するファイルを diff-match-patch を使用して比較します:
  - **インライン表示:** 標準の差分出力を提示します。
  - **サイドバイサイド表示:** 左側に元データ、右側に計算された差分を表示します。

  差分結果は HTML ファイルに変換され、`diff` ディレクトリに保存されます。

- **詳細なデバイス表示:**
  `/host/<hostname>` エンドポイントを通じて各デバイスの詳細情報にアクセスできます。

## ネットワークデバイスコマンドのカスタマイズ

NW-Diff では、ネットワークデバイスで実行されるコマンドをカスタマイズして、設定およびステータスデータをキャプチャできます。このセクションでは、異なるデバイスモデルのコマンドセットを変更または拡張する方法について説明します。

### コマンド設定ファイル

ネットワークデバイスで実行されるコマンドは、`src/nw_diff/devices.py` に定義されています。このファイルには以下が含まれます:

1. **`DEVICE_COMMANDS`** - デバイスモデルとそのコマンドセットをマッピングする辞書
2. **`DEFAULT_COMMANDS`** - デバイスモデルが認識されない場合に使用されるフォールバックコマンド

### コマンド構造の理解

`DEVICE_COMMANDS` 辞書は以下の構造を使用します:

```python
DEVICE_COMMANDS = {
    "fortinet": (
        "get system status",
        "diag switch physical-ports summary",
        "diag switch trunk summary",
        "diag switch trunk list",
        "diag stp vlan list",
    ),
    "cisco": (
        "show version",
        "show running-config",
    ),
    "junos": (
        "show chassis hardware",
        "show route",
    ),
}
```

- **キー**: デバイスモデル名（`hosts.csv` の `model` 列と一致する小文字の文字列）
- **値**: そのモデルのデバイスで実行するコマンド文字列のタプル

### コマンドの変更方法

#### 既存のデバイスモデルへのコマンド追加

既存のデバイスモデルにコマンドを追加するには、`DEVICE_COMMANDS` の対応するタプルを編集します:

```python
# 変更前
"cisco": (
    "show version",
    "show running-config",
),

# 変更後 - "show interfaces status" を追加
"cisco": (
    "show version",
    "show running-config",
    "show interfaces status",
),
```

**重要**: Python タプル構文のため、最後のコマンドの後にカンマを付けてください。

#### 新しいデバイスモデルの追加

新しいデバイスモデルをサポートするには、`DEVICE_COMMANDS` 辞書に新しいエントリを追加します:

```python
DEVICE_COMMANDS = {
    # ... 既存のモデル ...
    "arista": (
        "show version",
        "show running-config",
        "show interfaces status",
    ),
}
```

次に、`hosts.csv` の `model` 列が新しいキー（例: `arista`）と一致することを確認してください。

#### デフォルトコマンドの変更

認識されないデバイスモデルに使用されるフォールバックコマンドを変更する場合は、`DEFAULT_COMMANDS` タプルを編集します:

```python
# 変更前
DEFAULT_COMMANDS = ("show version",)

# 変更後
DEFAULT_COMMANDS = (
    "show version",
    "show system information",
)
```

### ベストプラクティスと安全ガイドライン

1. **最初に手動でコマンドをテストする**
   - `devices.py` にコマンドを追加する前に、デバイスで手動でテストして、正しく動作し、障害を引き起こさないことを確認してください
   - コマンドが **読み取り専用** であり、デバイス設定を変更しないことを確認してください

2. **読み取り専用コマンドを使用する**
   - 情報を取得するコマンドのみを使用してください（例: `show`、`get`、`display`）
   - デバイス設定を変更する可能性のある設定コマンド（例: `config`、`set`、`configure`）は **決して** 使用しないでください
   - デバイスパフォーマンスに影響を与える可能性のあるコマンド（例: 本番環境での `debug` コマンド）は避けてください

3. **コマンド出力サイズを考慮する**
   - 非常に大きな出力を生成するコマンドは、大量のストレージとメモリを消費する可能性があることに注意してください
   - コマンド出力をテストして、管理可能であることを確認してください
   - 必要に応じて、フィルタまたは特定のクエリを使用して出力サイズを制限することを検討してください

4. **デバイスベンダーの規則に従う**
   - 各デバイスベンダーの正しいコマンド構文を使用してください
   - 適切なコマンドの使用法については、ベンダーのドキュメントを参照してください
   - コマンドの特権レベル要件に注意してください

5. **一貫した書式を維持する**
   - コマンドコレクションにはタプル（リストではなく）を使用してください
   - 単一項目のタプルには末尾のカンマを含めてください: `("command",)`
   - `hosts.csv` のエントリと一致するように、デバイスモデルキーには小文字を使用してください

6. **変更を文書化する**
   - 特定のコマンドが追加または変更された理由を説明するコメントを追加してください
   - コンプライアンスまたは監視の目的で重要なコマンドの記録を保持してください

7. **変更前にバックアップする**
   - 変更を加える前に、常に `devices.py` のバックアップを保持してください
   - 本番環境にデプロイする前に、開発環境で変更をテストしてください

### 例: 完全な変更

新しいデバイスモデルを追加し、既存のモデルを変更する完全な例を次に示します:

```python
# src/nw_diff/devices.py 内

DEVICE_COMMANDS = {
    "fortinet": (
        "get system status",
        "diag switch physical-ports summary",
        "diag switch trunk summary",
        "diag switch trunk list",
        "diag stp vlan list",
        # アップリンクステータスの監視のため追加
        "get system interface physical",
    ),
    "cisco": (
        "show version",
        "show running-config",
    ),
    "junos": (
        "show chassis hardware",
        "show route",
    ),
    # 新しいデバイスモデルを追加
    "arista": (
        "show version",
        "show running-config",
        "show interfaces status",
        "show lldp neighbors",
    ),
}

DEFAULT_COMMANDS = ("show version",)
```

### 変更の確認

`devices.py` を変更した後:

1. **構文チェック**: Python 構文の検証を実行
   ```bash
   python -m py_compile src/nw_diff/devices.py
   ```

2. **リンティング**: コード品質をチェック
   ```bash
   pylint src/nw_diff/devices.py
   ```

3. **キャプチャテスト**: アプリケーションが新しいコマンドを実行できることを確認
   - アプリケーションを起動
   - 変更されたモデルを使用するデバイスの `/capture/origin/<hostname>` または `/capture/dest/<hostname>` エンドポイントを使用
   - `origin` または `dest` ディレクトリの出力ファイルを確認
   - エラーがないかログを確認

4. **アプリケーションの再起動**: `devices.py` の変更を有効にするには、アプリケーションの再起動が必要です
   ```bash
   # ローカルで実行している場合
   # 現在のプロセスを停止（Ctrl+C）して再起動
   python run_app.py

   # Docker で実行している場合
   docker-compose restart
   ```

### トラブルシューティング

**コマンドが実行されない:**
- `hosts.csv` のデバイスモデルが `DEVICE_COMMANDS` のキーと一致することを確認してください（大文字小文字は区別されません）
- 接続エラーまたはコマンド失敗については、アプリケーションログを確認してください
- デバイスの認証情報が環境変数で正しいことを確認してください

**構文エラー:**
- タプル構文（末尾のカンマ、適切な括弧）を確認してください
- すべての文字列が適切に引用符で囲まれていることを確認してください
- `python -m py_compile src/nw_diff/devices.py` を実行して構文エラーをチェックしてください

**デバイスでの権限エラー:**
- ユーザーアカウントがコマンドを実行するための十分な特権を持っていることを確認してください
- 一部のコマンドには、有効化モードまたは特定のユーザーロールが必要な場合があります

## インストール

1. **リポジトリのクローン:**
   ```bash
   git clone https://github.com/yourusername/nw-diff.git
   ```
2. **プロジェクトディレクトリに移動:**
   ```bash
   cd nw-diff
   ```

3. **依存関係のインストール:**
   Python がインストールされていることを確認し、必要なパッケージをインストールします:
   ```bash
   pip install -r requirements.txt
   ```
   必要なパッケージには Flask、Netmiko、diff-match-patch が含まれます。

4. **環境変数の設定:**
   - デバイス接続に必要なパスワードを設定するため、`DEVICE_PASSWORD` 環境変数を設定します:
     ```bash
     export DEVICE_PASSWORD=your_device_password
     ```
   - **機密性の高い API エンドポイント（キャプチャ、ログ、エクスポート）を保護するため、`NW_DIFF_API_TOKEN` 環境変数を設定します**:
     ```bash
     export NW_DIFF_API_TOKEN=your_secure_random_token
     ```
     安全なトークンを生成するには:
     ```bash
     python -c "import secrets; print(secrets.token_urlsafe(32))"
     ```

     **重要:** `NW_DIFF_API_TOKEN` が設定されていない場合、機密性の高いエンドポイントは認証なしでアクセス可能になります（本番環境では推奨されません）。

   - **（オプション）ブラウザベースの保護されたエンドポイントへのアクセスに HTTP Basic 認証を設定します**:
     ```bash
     export NW_DIFF_BASIC_USER=your_username
     ```

     **本番環境**では、ハッシュ化されたパスワードを使用します（推奨）:
     ```bash
     # Python を使用してパスワードハッシュを生成
     python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('your_password'))"
     export NW_DIFF_BASIC_PASSWORD_HASH='<generated_hash>'
     ```

     **開発環境のみ**では、プレーンパスワードを使用できます（本番環境では推奨されません）:
     ```bash
     export NW_DIFF_BASIC_PASSWORD=your_plain_password
     ```

     **注意:** Basic 認証は `NW_DIFF_API_TOKEN` が設定されている場合にのみ適用されます。保護されたエンドポイントには、Bearer トークン（`Authorization: Bearer <token>`）と Basic 認証（`Authorization: Basic <base64(user:pass)>`）の両方が受け入れられます。

   - **（オプション）ホストインベントリファイルのカスタム場所を指定するため、`HOSTS_CSV` 環境変数を設定します**:
     ```bash
     export HOSTS_CSV=/path/to/hosts.csv
     ```
     設定されていない場合、アプリケーションは現在のディレクトリのデフォルトの `hosts.csv` を使用します。

     **利点:** リポジトリの外にホストインベントリを保存することで、機密データ（IP アドレス、ユーザー名、デバイスモデル）の誤ったコミットを防ぎ、セキュリティが向上します。これは、インベントリをシークレットまたは設定ボリュームとしてマウントできる本番デプロイメントに特に有用です。

     **コンテナの例:**
     ```bash
     docker run -v /secure/path/hosts.csv:/app/hosts.csv -e HOSTS_CSV=/app/hosts.csv ...
     ```

## 使用方法

### 実行モードの概要

アプリケーションは 2 つの主要な実行モードをサポートしています:

1. **ローカル開発モード**: シングルユーザーの開発とテスト用に `127.0.0.1:5000`（localhost のみ）にバインドします。これが安全なデフォルトです。
2. **コンテナ/本番モード**: コンテナネットワークまたはリバースプロキシ（nginx）からのアクセスを許可するために `0.0.0.0:5000` にバインドします。Docker デプロイメントに必要です。

アプリケーションには **ProxyFix ミドルウェア**が含まれており、リバースプロキシ（nginx など）からの `X-Forwarded-*` ヘッダーを正しく処理し、プロキシの背後にデプロイされた場合の適切な URL 生成、HTTPS 検出、クライアント IP ロギングを保証します。

### 本番モードでの実行（デフォルト）

デフォルトでは、セキュリティのため Flask デバッグモードが**無効**になっており、**127.0.0.1**（localhost のみ）にバインドします:

1. **アプリケーションの起動:**
   ```bash
   python run_app.py
   ```
   またはソースから直接:
   ```bash
   PYTHONPATH=src python -m nw_diff.app
   ```
2. **アプリケーションへのアクセス:**
   ブラウザで [http://localhost:5000](http://localhost:5000) にアクセスします。

### 開発モードでの実行

ローカル開発では、`APP_DEBUG` 環境変数を設定してデバッグモードを有効にできます:

1. **デバッグモードで実行:**
   ```bash
   export APP_DEBUG=true
   python run_app.py
   ```
   またはインラインで実行:
   ```bash
   APP_DEBUG=true python run_app.py
   ```
2. **アプリケーションへのアクセス:**
   ブラウザで [http://localhost:5000](http://localhost:5000) にアクセスします。

**注意:** デバッグモードは機密情報を公開しセキュリティ脆弱性を生む可能性があるため、本番環境では**決して**有効にしないでください。

### バインドホストとポートのカスタマイズ

環境変数を使用してバインドホストとポートをカスタマイズできます:

- `FLASK_RUN_HOST`: バインドするホスト（デフォルト: ローカル開発用に `127.0.0.1`）
- `FLASK_RUN_PORT`: バインドするポート（デフォルト: `5000`）

**例:**

```bash
# すべてのインターフェースにバインド（コンテナ環境で有用）
FLASK_RUN_HOST=0.0.0.0 python run_app.py

# 異なるポートを使用
FLASK_RUN_PORT=8080 python run_app.py

# 複数の設定を組み合わせる
FLASK_RUN_HOST=0.0.0.0 FLASK_RUN_PORT=8080 APP_DEBUG=false python run_app.py
```

**セキュリティ注意:** リバースプロキシなしでローカルで実行する場合は、不正なネットワークアクセスを防ぐためにデフォルトの `127.0.0.1` を使用してください。コンテナ環境内または適切に設定された認証付きリバースプロキシの背後でのみ `0.0.0.0` を使用してください。

### エンドポイントとの連携

#### 公開エンドポイント（認証不要）
- **ホスト一覧の表示:** `/`（ホームページ）
- **詳細なデバイス情報の表示:** `/host/<hostname>`
- **ファイルの比較:** `/compare_files`

#### 保護されたエンドポイント（認証が必要）
以下のエンドポイントは `NW_DIFF_API_TOKEN` が設定されている場合に認証が必要です。Bearer トークンと Basic 認証の両方がサポートされています:
- **データキャプチャ:**
  - 元データ: `/capture/origin/<hostname>`
  - 宛先データ: `/capture/dest/<hostname>`
  - 全デバイス: `/capture_all/origin` または `/capture_all/dest`
- **ログの表示:**
  - Web UI: `/logs`
  - API: `/api/logs`
- **データのエクスポート:**
  - HTML エクスポート: `/export/<hostname>`
  - JSON API: `/api/export/<hostname>`

**Bearer トークンを使用した curl の例:**
```bash
curl -H "Authorization: Bearer your_token_here" http://localhost:5000/api/logs
```

**Basic 認証を使用した curl の例:**
```bash
curl -u username:password http://localhost:5000/api/logs
```

**ブラウザを使用した例:**
ブラウザで保護されたエンドポイントにアクセスする場合、Basic 認証が設定されていれば、ユーザー名とパスワードの入力を求められます。ブラウザは自動的に資格情報を Basic 認証ヘッダーとしてエンコードします。

**注意:** `NW_DIFF_API_TOKEN` が設定されていない場合、これらのエンドポイントは認証なしで動作します（本番環境では推奨されません）。

### 差分結果の確認

計算された差分 HTML ファイルは `diff` ディレクトリに保存され、オフラインで確認できます。

## Docker デプロイメント

NW-Diff は Docker と docker-compose を介した HTTPS（TLS 終端）およびオプションの Basic 認証を使用したコンテナ化デプロイメントをサポートしています。これにより、安全で本番環境に対応したデプロイメントオプションが提供されます。

**アーキテクチャ概要:**
- **nginx**: TLS 終端を伴うリバースプロキシとして機能し、`X-Forwarded-*` ヘッダーを設定します
- **Flask アプリ**: ProxyFix ミドルウェアを使用して、転送されたヘッダーを正しく解釈します
- **コンテナバインディング**: Flask はコンテナ内で `0.0.0.0:5000` にバインドします（`FLASK_RUN_HOST` 経由で設定）
- **ネットワーク分離**: nginx のみがホストに公開され、Flask アプリは Docker ネットワーク内でのみアクセス可能です

ProxyFix ミドルウェアにより、Flask アプリが nginx リバースプロキシの背後で実行されている場合に、元のリクエストプロトコル（HTTPS）、ホスト、クライアント IP を正しく検出できます。

### 前提条件

- Docker と Docker Compose がインストールされていること
- OpenSSL（自己署名証明書の生成用）
- Apache Utils（htpasswd ファイルの生成用） - `apt-get install apache2-utils` または `yum install httpd-tools`

### クイックスタート

1. **リポジトリのクローンとプロジェクトディレクトリへの移動:**
   ```bash
   git clone https://github.com/icecake0141/nw-diff.git
   cd nw-diff
   ```

2. **環境変数の設定:**
   ```bash
   cp .env.example .env
   # .env を編集して DEVICE_PASSWORD と NW_DIFF_API_TOKEN を設定
   ```

3. **TLS 証明書と Basic 認証の生成（自動化）:**

   **オプション A: 自動セットアップ（CI/CD に推奨）**
   ```bash
   # 環境変数を設定
   export NW_DIFF_BASIC_USER=admin
   export NW_DIFF_BASIC_PASSWORD=your_strong_password
   export CERT_HOSTNAME=myserver.example.com  # オプション、デフォルトは localhost

   # 自動初期化スクリプトを実行
   ./docker/nginx/init-certs-and-htpasswd.sh
   ```
   このスクリプトは以下を実行します:
   - 自己署名 TLS 証明書を生成（開発/デモ用）
   - 提供された資格情報で .htpasswd ファイルを作成
   - ファイル権限と設定を検証
   - セキュリティ警告とリマインダーを表示

   **オプション B: 対話型セットアップ**
   ```bash
   # 証明書を対話的に生成
   ./scripts/mk-certs.sh
   # プロンプトに従って証明書を生成
   # またはホスト名を指定: CERT_HOSTNAME=myserver.example.com ./scripts/mk-certs.sh

   # Basic 認証資格情報を対話的に生成
   ./scripts/mk-htpasswd.sh
   # プロンプトに従ってユーザー名/パスワードを作成
   ```

4. **hosts.csv インベントリファイルの作成:**
   ```bash
   cp hosts.csv.sample hosts.csv
   # デバイス情報で hosts.csv を編集
   ```

5. **アプリケーションスタックの起動:**
   ```bash
   docker-compose up -d
   ```

6. **アプリケーションへのアクセス:**
   - HTTPS: `https://localhost/`（自己署名証明書の警告を受け入れる必要があります）
   - Basic 認証資格情報の入力を求められます

7. **ログの表示:**
   ```bash
   docker-compose logs -f
   ```

8. **アプリケーションの停止:**
   ```bash
   docker-compose down
   ```

### 設定

#### 環境変数

`.env` ファイルで以下を設定します:

- `DEVICE_PASSWORD`: ネットワークデバイスへの SSH 接続用パスワード
- `NW_DIFF_API_TOKEN`: API 認証用の安全なトークン（`python -c "import secrets; print(secrets.token_urlsafe(32))"` で生成）
- `NW_DIFF_BASIC_USER`: （オプション）HTTP Basic 認証用のユーザー名
- `NW_DIFF_BASIC_PASSWORD_HASH`: （オプション）Basic 認証用のハッシュ化されたパスワード（`python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('password'))"` で生成）
- `NW_DIFF_BASIC_PASSWORD`: （オプション）Basic 認証用のプレーンパスワード（開発のみ - 本番環境ではハッシュ化されたパスワードを使用）
- `APP_DEBUG`: 本番環境では `false` に設定（デフォルト）
- `HOSTS_CSV`: ホストインベントリファイルへのオプションのカスタムパス

**認証モード:**
- `NW_DIFF_API_TOKEN` が設定されていない場合: 認証不要（レガシーモード）
- `NW_DIFF_API_TOKEN` が設定されている場合:
  - API クライアントは Bearer トークンを使用可能: `Authorization: Bearer <token>`
  - ブラウザユーザーは Basic 認証を使用可能: `Authorization: Basic <base64(user:pass)>`
  - 保護されたエンドポイント（キャプチャ、ログ、エクスポート）には両方の方法が受け入れられます

#### TLS/SSL 証明書

**開発/テスト用**には、提供されたスクリプトを使用して自己署名証明書を生成します:
```bash
./scripts/mk-certs.sh
```

**本番環境**では以下を行う必要があります:
- 信頼された認証局（CA）からの証明書を使用するか、または
- Caddy または certbot で Let's Encrypt を使用するか、または
- 既存の証明書をマウントします:
  ```bash
  # 証明書を docker/certs/ に配置
  cp /path/to/your/cert.pem docker/certs/cert.pem
  cp /path/to/your/key.pem docker/certs/key.pem
  chmod 644 docker/certs/cert.pem
  chmod 600 docker/certs/key.pem
  ```

#### Basic 認証

Basic 認証はデフォルトですべてのエンドポイントで有効です。ユーザーを管理するには:

**ユーザーを追加:**
```bash
./scripts/mk-htpasswd.sh
```

**追加ユーザーを追加:**
```bash
htpasswd docker/.htpasswd <username>
```

**Basic 認証を無効化（本番環境では推奨されません）:**
`docker/nginx.conf` を編集して以下の行をコメントアウトします:
```nginx
# auth_basic "NW-Diff Access";
# auth_basic_user_file /etc/nginx/.htpasswd;
```
その後再起動: `docker-compose restart nginx`

#### 永続データ

永続ストレージには Docker ボリュームが使用されます:
- `nw-diff-logs`: アプリケーションログ
- `nw-diff-dest`: 宛先設定スナップショット
- `nw-diff-origin`: 元の設定スナップショット
- `nw-diff-diff`: 生成された差分ファイル
- `nw-diff-backup`: 設定バックアップ

データをバックアップまたは移行するには:
```bash
# ボリュームのバックアップ
docker run --rm -v nw-diff-logs:/data -v $(pwd):/backup alpine tar czf /backup/nw-diff-logs-backup.tar.gz -C /data .

# ボリュームの復元
docker run --rm -v nw-diff-logs:/data -v $(pwd):/backup alpine tar xzf /backup/nw-diff-logs-backup.tar.gz -C /data
```

### セキュリティのベストプラクティス

#### 概要
NW-Diff はセキュリティを優先して設計されていますが、適切なデプロイメントには慎重な設定が必要です。このセクションでは、本番デプロイメントの重要なセキュリティ対策について概説します。

#### TLS/SSL 証明書

**開発/デモ環境:**
- 提供された自己署名証明書生成を使用:
  ```bash
  ./scripts/mk-certs.sh
  # または自動セットアップ用
  ./docker/nginx/init-certs-and-htpasswd.sh
  ```
- ブラウザのセキュリティ警告を受け入れる（自己署名証明書では予想される）
- 本番環境では自己署名証明書を**決して**使用しないでください

**本番環境:**
- **推奨**: Let's Encrypt（無料、自動化、広く信頼されている）
  - certbot または類似ツールを使用して自動更新
  - certbot の例:
    ```bash
    certbot certonly --standalone -d yourdomain.com
    cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem docker/certs/cert.pem
    cp /etc/letsencrypt/live/yourdomain.com/privkey.pem docker/certs/key.pem
    ```
- **代替**: 商用 CA（DigiCert、Sectigo、GlobalSign など）
- **エンタープライズ**: 内部 PKI/CA インフラストラクチャ
- **重要**: 信頼された証明書をインストールした後、`docker/nginx.conf` で HSTS を有効にします:
  ```nginx
  add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
  ```
- **警告**: 自己署名証明書で HSTS を有効にしないでください - 永続的なブラウザの問題を引き起こします

#### 認証と認可

**API トークンセキュリティ:**
1. 強力でランダムなトークンを生成:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
2. 環境変数またはシークレットマネージャーに保存（コードには決して保存しない）
3. 開発/ステージング/本番環境で異なるトークンを使用
4. 定期的にトークンをローテーション（90 日ごとを推奨）
5. トークンを含む `.env` ファイルを決してコミットしない

**Basic 認証:**
1. 強力なパスワードを使用（最低 12 文字、大文字小文字、数字、記号を混在）
2. ハッシュ化されたパスワードを生成:
   ```bash
   ./scripts/mk-htpasswd.sh
   # または自動デプロイメント用
   export NW_DIFF_BASIC_USER=admin
   export NW_DIFF_BASIC_PASSWORD=your_strong_password
   ./docker/nginx/init-certs-and-htpasswd.sh
   ```
3. `docker/.htpasswd` をバージョン管理に**決して**コミットしない（`.gitignore` でカバー）
4. 可能であればアカウントロックアウトポリシーを実装（nginx モジュールまたは WAF 経由）

**デバイス資格情報:**
1. `DEVICE_PASSWORD` を安全に保存（シークレットマネージャー、暗号化されたボールト）
2. 可能な場合はネットワークデバイスで読み取り専用アカウントを使用
3. サポートされている場合はパスワードの代わりに SSH キー認証を実装
4. デバイス資格情報を定期的にローテーション

#### ネットワークセキュリティ

1. **ファイアウォール設定:**
   - HTTPS（443）アクセスを承認されたネットワーク/IP に制限
   - 不要な場合は HTTP（80）ポートを閉じる（オプション、デフォルトで HTTPS にリダイレクト）
   - リモートアクセスには VPN またはバスティオンホストを使用

2. **リバースプロキシの強化:**
   - nginx 設定にはデフォルトでレート制限が含まれています
   - 使用パターンに基づいて `docker/nginx.conf` でレート制限を調整:
     ```nginx
     limit_req_zone $binary_remote_addr zone=general:10m rate=10r/s;
     limit_req_zone $binary_remote_addr zone=api:10m rate=5r/s;
     ```
   - 追加保護のために WAF（Web Application Firewall）の追加を検討

3. **コンテナセキュリティ:**
   - 可能な場合はコンテナを非 root ユーザーとして実行
   - 環境変数の代わりに機密データに Docker シークレットを使用
   - 定期的にコンテナイメージの脆弱性をスキャン:
     ```bash
     docker scan nw-diff:latest
     ```

#### データ保護

1. **機密ファイルの処理:**
   - `.gitignore` が以下を除外することを確認: `docker/.htpasswd`、`docker/certs/`、`.env`、`hosts.csv`
   - 本番環境ではデバイスインベントリ（`hosts.csv`）をリポジトリ外に保存
   - 機密データにはボリュームマウントを使用:
     ```bash
     docker run -v /secure/path/hosts.csv:/app/hosts.csv:ro -e HOSTS_CSV=/app/hosts.csv ...
     ```

2. **シークレット管理:**
   - 環境固有のシークレットを使用（開発 vs. 本番）
   - Docker シークレット、Kubernetes シークレット、または専用シークレットマネージャー（HashiCorp Vault、AWS Secrets Manager など）の使用を検討
   - エラーメッセージでシークレットをログまたは公開しない

3. **設定バックアップ:**
   - 設定データのバックアップを暗号化
   - 安全でアクセス制御されたロケーションにバックアップを保存
   - コンプライアンスのための保持ポリシーを実装

#### モニタリングと監査

1. **ログ管理:**
   - nginx アクセス/エラーログを定期的に確認:
     ```bash
     docker-compose logs nginx | grep -E "40[134]|50[0-3]"
     ```
   - 疑わしいアクティビティを監視: 繰り返される 401/403 エラー、異常なトラフィックパターン
   - 集中ログ（ELK スタック、Splunk など）を検討

2. **セキュリティ監査:**
   - 定期的にセキュリティスキャンを実行:
     ```bash
     pip-audit -r requirements.txt
     docker scan nw-diff:latest
     ```
   - 四半期ごとに依存関係を確認して更新
   - Flask、nginx、依存関係のセキュリティアドバイザリを購読

3. **アクセス監視:**
   - すべてのキャプチャ操作と設定変更をログ
   - 不正アクセス試行のアラートを実装
   - 定期的なアクセスレビュー（資格情報、トークンなどを持つユーザー）

#### 定期的なメンテナンス

1. **更新:**
   - ベース Docker イメージを最新に保つ: `docker-compose pull`
   - Python 依存関係を更新: `pip install -r requirements.txt --upgrade`
   - セキュリティアドバイザリと CVE を監視

2. **証明書の更新:**
   - Let's Encrypt 証明書は 90 日ごとに期限切れ - 更新を自動化
   - 手動証明書更新のカレンダーリマインダーを設定
   - 定期的に証明書の有効性をテスト:
     ```bash
     openssl x509 -in docker/certs/cert.pem -noout -enddate
     ```

3. **資格情報のローテーション:**
   - 90 日ごとに API トークンをローテーション
   - 180 日ごとに Basic 認証パスワードを更新
   - 組織のポリシーに従ってデバイスパスワードを変更

#### 本番デプロイメントチェックリスト

本番環境にデプロイする前に確認:

- [ ] 信頼された TLS 証明書を使用（自己署名ではない）
- [ ] `docker/nginx.conf` で HSTS ヘッダーが有効
- [ ] すべての認証に強力で一意のパスワード
- [ ] API トークンが生成され安全に保存されている
- [ ] `.env` ファイルがバージョン管理にコミットされていない
- [ ] `hosts.csv` がリポジトリ外に保存されているか適切に保護されている
- [ ] アクセスを制限するファイアウォールルールが設定されている
- [ ] コンテナイメージの脆弱性がスキャンされている
- [ ] ログが収集され監視されている
- [ ] バックアップ戦略が実装されテストされている
- [ ] デバッグモードが無効（`APP_DEBUG=false`）
- [ ] すべての依存関係の最新安定バージョンを実行
- [ ] インシデント対応計画が文書化されている

#### デモ vs. 本番設定

**デモ/開発環境:**
- 自己署名証明書が許容される
- HSTS が無効（コメントアウト）
- Basic 認証はオプション
- ローカルテスト用に `127.0.0.1` にバインド
- デバッグモードを一時的に有効にできる
- より緩やかなレート制限

**本番環境:**
- 信頼された TLS 証明書を**使用する必要があります**
- HSTS ヘッダーを**有効にする必要があります**
- Basic 認証 + API トークンを**使用する必要があります**
- コンテナ内でのみ `0.0.0.0` にバインド（nginx プロキシ）
- デバッグモードを**無効にする必要があります**
- 厳格なレート制限と監視
- 定期的なセキュリティ監査と更新

#### セキュリティ問題の報告

NW-Diff でセキュリティ脆弱性を発見した場合:
1. 公開 GitHub issue を**開かない**
2. リポジトリメンテナーにセキュリティ上の懸念をプライベートにメール
3. 詳細な情報を含める: 再現手順、影響評価
4. 公開開示前に修正のための合理的な時間を許可

### トラブルシューティング

**ブラウザでの証明書エラー:**
- 自己署名証明書は警告を表示します - これは開発では予想されます
- ブラウザで例外を追加するか、システム信頼ストアに証明書をインポート（scripts/mk-certs.sh の出力を参照）

**接続拒否:**
- コンテナが実行されていることを確認: `docker-compose ps`
- ログを確認: `docker-compose logs`

**認証失敗:**
- .htpasswd ファイルが存在することを確認: `ls -la docker/.htpasswd`
- 資格情報をテスト: `htpasswd -v docker/.htpasswd <username>`

**権限エラー:**
- 証明書ファイルに正しい権限があることを確認（cert.pem: 644、key.pem: 600）
- ボリューム権限を確認: `docker-compose exec nw-diff ls -la /app`

**Docker ビルド SSL 証明書エラー:**
- SSL インターセプトを伴う企業/CI 環境でビルドする場合は、以下を使用:
  ```bash
  docker build --build-arg SKIP_PIP_SSL_VERIFY=1 -t nw-diff:latest .
  ```
- これにより、pip インストール中に PyPI ドメインの `--trusted-host` フラグが追加されます
- **注意:** 信頼できる環境でのみこの回避策を使用してください; SSL 検証をバイパスします

## 開発

### ローカル開発セットアップ

1. **開発用依存関係のインストール:**
   ```bash
   pip install -r requirements.txt -r requirements-dev.txt
   ```

2. **セキュリティ監査の実行:**
   ```bash
   pip-audit -r requirements.txt -r requirements-dev.txt
   ```

3. **フォーマット、lint、型チェック、テスト:**
   ```bash
   black src tests
   pylint src tests
   mypy src tests
   pytest
   ```

4. **pre-commit フックの実行:**
   ```bash
   pre-commit run --all-files
   ```

### テスト

NW-Diff には品質とセキュリティを保証するための包括的なテストカバレッジが含まれています:

#### ユニットおよび統合テスト

ローカルで完全なテストスイートを実行:
```bash
pytest -v
```

テストスイートには以下が含まれます:
- **ユニットテスト**: コアアプリケーションロジック、認証、認可
- **統合テスト**: Docker デプロイメント設定、セキュリティ設定
- **型チェック**: mypy による静的型分析
- **Lint**: pylint によるコード品質チェック
- **フォーマット**: black によるコードスタイル検証

#### フルスタック統合テスト（CI）

プロジェクトには完全な Docker Compose デプロイメントを検証する自動エンドツーエンドテストが含まれています:

**テストされる内容:**
- ✅ Docker Compose が正常にビルドされる
- ✅ HTTPS（TLS/SSL）が有効で機能している
- ✅ HTTP が正しく HTTPS にリダイレクトされる
- ✅ Basic 認証が必要で機能している
- ✅ 保護されたエンドポイントでの Bearer トークン認証
- ✅ 無効な資格情報が拒否される（401 応答）
- ✅ 有効な資格情報がアクセスを許可する（200 応答）
- ✅ 自己署名証明書が正しく生成される
- ✅ すべてのセキュリティヘッダーが存在する
- ✅ サービスが正常に開始され安定したままである

**統合テストをローカルで実行:**

1. **スタックのセットアップと起動:**
   ```bash
   # 証明書と .htpasswd を生成
   export NW_DIFF_BASIC_USER=admin
   export NW_DIFF_BASIC_PASSWORD=yourpassword
   ./docker/nginx/init-certs-and-htpasswd.sh

   # hosts.csv を作成（またはサンプルからコピー）
   cp hosts.csv.sample hosts.csv

   # .env で環境変数を設定
   cp .env.example .env
   # 値で .env を編集

   # スタックを起動
   docker-compose up -d
   ```

2. **統合テストスクリプトを実行:**
   ```bash
   export NW_DIFF_BASIC_USER=admin
   export NW_DIFF_BASIC_PASSWORD=yourpassword
   export NW_DIFF_API_TOKEN=your_token_here
   ./scripts/test-integration.sh
   ```

3. **クリーンアップ:**
   ```bash
   docker-compose down -v
   ```

#### 継続的インテグレーション

プロジェクトはすべてのプッシュとプルリクエストで自動テストのために GitHub Actions を使用します:

- **CI ワークフロー**（`.github/workflows/ci.yml`）: ユニットテスト、lint、型チェック、セキュリティ監査を実行
- **統合ワークフロー**（`.github/workflows/integration.yml`）: HTTPS と認証検証を伴うフルスタック Docker Compose テストを実行

テスト結果を表示: [GitHub Actions](https://github.com/icecake0141/nw-diff/actions)

#### テストカバレッジ

テストは以下をカバーします:
- Flask アプリケーションのルートと認証ロジック
- Docker と nginx の設定検証
- TLS/SSL 証明書のセットアップと検証
- Basic 認証と Bearer トークンフロー
- セキュリティヘッダーと HTTP ステータスコード
- ファイル権限と .gitignore ルール
- SPDX ライセンスヘッダーと LLM 帰属

#### テストの記述

貢献する場合は、以下をお願いします:
- 新機能またはバグ修正のテストを追加
- PR を提出する前にすべてのテストがローカルで合格することを確認
- `tests/` ディレクトリの既存のテストパターンに従う
- テストファイルに SPDX ヘッダーと LLM 帰属を含める
- ポジティブケースとネガティブケースの両方をテスト（成功と失敗のシナリオ）

### Pre-commit フック

コード品質を保証するために pre-commit フックを実行:
```bash
pre-commit run --all-files
```
