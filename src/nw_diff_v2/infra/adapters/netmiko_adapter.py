"""Netmiko adapter for device command capture."""

from __future__ import annotations

from typing import Any


class NetmikoAdapter:  # pylint: disable=too-few-public-methods
    """Thin adapter around Netmiko for easier service-level mocking."""

    def capture_commands(
        self,
        *,
        device_type: str,
        host: str,
        username: str,
        port: int,
        password: str,
        commands: list[str],
    ) -> dict[str, str]:
        """Run commands on a device and return command-output mapping."""
        # pylint: disable=import-outside-toplevel
        from netmiko import ConnectHandler

        connection: Any = None
        outputs: dict[str, str] = {}
        try:
            connection = ConnectHandler(
                device_type=device_type,
                host=host,
                username=username,
                port=port,
                password=password,
            )
            connection.enable()
            for command in commands:
                outputs[command] = connection.send_command(command, read_timeout=10)
            return outputs
        finally:
            if connection is not None:
                try:
                    connection.disconnect()
                except Exception:  # pylint: disable=broad-exception-caught
                    pass
