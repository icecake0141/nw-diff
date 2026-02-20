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

NW-Diff is a Flask-based web application designed to retrieve, compare, and display configuration or status data collected from network devices. It leverages Netmiko to connect to devices and capture data defined in a CSV file. Using diff-match-patch, the application computes differences between two sets of data and presents the results in both inline and side-by-side views. Diff HTML files are generated and stored in a dedicated "diff" directory for subsequent review.

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
   python run_app.py

   # If running with Docker
   docker-compose restart
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
   pip install -r requirements.txt
   ```
   This installs Flask, Netmiko, diff-match-patch, and other required packages.

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
   python run_app.py
   ```
   The application will start on `http://127.0.0.1:5000` by default.

9. **Access the application:**
   Open your web browser and navigate to [http://localhost:5000](http://localhost:5000)

### Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `DEVICE_PASSWORD` | Yes | Password for SSH connections to network devices |
| `NW_DIFF_API_TOKEN` | Recommended | Secure token for protecting sensitive API endpoints (capture, logs, export) |
| `NW_DIFF_BASIC_USER` | Optional | Username for HTTP Basic Authentication |
| `NW_DIFF_BASIC_PASSWORD` | Optional | Password for HTTP Basic Authentication |
| `HOSTS_CSV` | Optional | Custom path to hosts inventory file (default: `hosts.csv`) |
| `FLASK_RUN_HOST` | Optional | Host to bind to (default: `127.0.0.1`) |
| `FLASK_RUN_PORT` | Optional | Port to bind to (default: `5000`) |
| `APP_DEBUG` | Optional | Enable debug mode (`true`/`false`, default: `false`) - **Never use in production** |

## Usage

### Running Modes Overview

The application supports two primary running modes:

1. **Local Development Mode**: Binds to `127.0.0.1:5000` (localhost only) for single-user development and testing. This is the secure default.
2. **Container/Production Mode**: Binds to `0.0.0.0:5000` to allow access from the container network or reverse proxy (nginx). Required for Docker deployments.

The application includes **ProxyFix middleware** to correctly handle `X-Forwarded-*` headers from reverse proxies (nginx, etc.), ensuring proper URL generation, HTTPS detection, and client IP logging when deployed behind a proxy.

### Running in Production Mode (Default)

By default, the application runs with Flask debug mode **disabled** for security and binds to **127.0.0.1** (localhost only):

1. **Run the Application:**
   ```bash
   python run_app.py
   ```
   Or directly from the source:
   ```bash
   PYTHONPATH=src python -m nw_diff.app
   ```
2. **Access the Application:**
   Open your browser and navigate to [http://localhost:5000](http://localhost:5000).

### Running in Development Mode

For local development, you can enable debug mode by setting the `APP_DEBUG` environment variable:

1. **Run with Debug Mode:**
   ```bash
   export APP_DEBUG=true
   python run_app.py
   ```
   Or run it inline:
   ```bash
   APP_DEBUG=true python run_app.py
   ```
2. **Access the Application:**
   Open your browser and navigate to [http://localhost:5000](http://localhost:5000).

**Note:** Debug mode should **never** be enabled in production environments as it can expose sensitive information and create security vulnerabilities.

### Customizing Bind Host and Port

You can customize the bind host and port using environment variables:

- `FLASK_RUN_HOST`: Host to bind to (default: `127.0.0.1` for local dev)
- `FLASK_RUN_PORT`: Port to bind to (default: `5000`)

**Examples:**

```bash
# Bind to all interfaces (useful for container environments)
FLASK_RUN_HOST=0.0.0.0 python run_app.py

# Use a different port
FLASK_RUN_PORT=8080 python run_app.py

# Combine multiple settings
FLASK_RUN_HOST=0.0.0.0 FLASK_RUN_PORT=8080 APP_DEBUG=false python run_app.py
```

**Security Note:** When running locally without a reverse proxy, use the default `127.0.0.1` to prevent unauthorized network access. Only use `0.0.0.0` in container environments or when behind a properly configured reverse proxy with authentication.

### Interacting with Endpoints

#### Public Endpoints (No Authentication Required)
- **View Host List:** `/` (homepage)
- **View Detailed Device Info:** `/host/<hostname>`
- **Compare Files:** `/compare_files`

#### Protected Endpoints (Require Authentication)
The following endpoints require authentication when `NW_DIFF_API_TOKEN` is set. Both Bearer token and Basic authentication are supported:
- **Capture Data:**
  - For origin data: `/capture/origin/<hostname>`
  - For destination data: `/capture/dest/<hostname>`
  - For all devices: `/capture_all/origin` or `/capture_all/dest`
- **View Logs:**
  - Web UI: `/logs`
  - API: `/api/logs`
- **Export Data:**
  - HTML export: `/export/<hostname>`
  - JSON API: `/api/export/<hostname>`

**Example using curl with Bearer token:**
```bash
curl -H "Authorization: Bearer your_token_here" http://localhost:5000/api/logs
```

**Example using curl with Basic authentication:**
```bash
curl -u username:password http://localhost:5000/api/logs
```

**Example using browser:**
When accessing protected endpoints in a browser, you'll be prompted for username and password if Basic Authentication is configured. The browser will automatically encode credentials as Basic auth headers.

**Note:** If `NW_DIFF_API_TOKEN` is not set, these endpoints will work without authentication (not recommended for production).

### Review Diff Results

The computed diff HTML files are stored in the `diff` directory for offline viewing.

## Docker Deployment

NW-Diff supports containerized deployment with HTTPS (TLS termination) and optional Basic Authentication via Docker and docker-compose. This provides a secure, production-ready deployment option.

**Architecture Overview:**
- **nginx**: Acts as a reverse proxy with TLS termination, sets `X-Forwarded-*` headers
- **Flask app**: Runs with ProxyFix middleware to correctly interpret forwarded headers
- **Container binding**: Flask binds to `0.0.0.0:5000` inside the container (set via `FLASK_RUN_HOST`)
- **Network isolation**: Only nginx is exposed to the host; Flask app is accessible only within the Docker network

The ProxyFix middleware ensures that the Flask app correctly detects the original request protocol (HTTPS), host, and client IP when running behind the nginx reverse proxy.

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
   docker-compose up -d
   ```

6. **Access the application:**
   - HTTPS: `https://localhost/` (you'll need to accept the self-signed certificate warning)
   - You'll be prompted for Basic Auth credentials

7. **View logs:**
   ```bash
   docker-compose logs -f
   ```

8. **Stop the application:**
   ```bash
   docker-compose down
   ```

### Configuration

#### Environment Variables

Set these in your `.env` file:

- `DEVICE_PASSWORD`: Password for SSH connections to network devices
- `NW_DIFF_API_TOKEN`: Secure token for API authentication (generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`)
- `NW_DIFF_BASIC_USER`: (Optional) Username for HTTP Basic Authentication
- `NW_DIFF_BASIC_PASSWORD_HASH`: (Optional) Hashed password for Basic Authentication (generate with `python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('password'))"`)
- `NW_DIFF_BASIC_PASSWORD`: (Optional) Plain password for Basic Authentication (development only - use hashed password in production)
- `APP_DEBUG`: Set to `false` in production (default)
- `HOSTS_CSV`: Optional custom path to hosts inventory file

**Authentication Modes:**
- If `NW_DIFF_API_TOKEN` is not set: No authentication required (legacy mode)
- If `NW_DIFF_API_TOKEN` is set:
  - API clients can use Bearer token: `Authorization: Bearer <token>`
  - Browser users can use Basic auth: `Authorization: Basic <base64(user:pass)>`
  - Both methods are accepted for protected endpoints (capture, logs, export)

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
- `nw-diff-dest`: Destination configuration snapshots
- `nw-diff-origin`: Origin configuration snapshots
- `nw-diff-diff`: Generated diff files
- `nw-diff-backup`: Configuration backups

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
