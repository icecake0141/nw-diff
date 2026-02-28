"""Host configuration repository backed by hosts.csv."""

from __future__ import annotations

import csv
import ipaddress
import re
from pathlib import Path

from nw_diff_v2.domain.models import HostRecord

HOST_RE = re.compile(r"^[a-zA-Z0-9._-]+$")
USER_RE = re.compile(r"^[a-zA-Z0-9._-]+$")
MODEL_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
REQUIRED_COLUMNS = {"host", "ip", "username", "port", "model"}
MAX_HOST_LEN = 253
MAX_USERNAME_LEN = 64
MAX_MODEL_LEN = 64


def load_hosts(csv_path: str) -> list[HostRecord]:
    """Load and validate hosts from CSV, skipping invalid rows."""
    rows: list[HostRecord] = []
    path = Path(csv_path)

    if not path.exists():
        return rows

    with path.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(
            line for line in csv_file if not line.lstrip().startswith("#")
        )
        if reader.fieldnames is None:
            return rows

        if REQUIRED_COLUMNS.difference(set(reader.fieldnames)):
            return rows

        for row in reader:
            host = (row.get("host") or "").strip()
            ip = (row.get("ip") or "").strip()
            username = (row.get("username") or "").strip()
            model = (row.get("model") or "").strip()
            port_text = (row.get("port") or "").strip()

            if not HOST_RE.match(host):
                continue
            if len(host) > MAX_HOST_LEN:
                continue

            try:
                ipaddress.ip_address(ip)
            except ValueError:
                continue

            if not USER_RE.match(username):
                continue
            if len(username) > MAX_USERNAME_LEN:
                continue
            if not MODEL_RE.match(model):
                continue
            if len(model) > MAX_MODEL_LEN:
                continue

            try:
                port = int(port_text)
            except ValueError:
                continue
            if port < 1 or port > 65535:
                continue

            rows.append(
                HostRecord(
                    host=host, ip=ip, username=username, port=port, model=model
                )
            )

    return rows
