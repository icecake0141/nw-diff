"""Runtime configuration for the v2 scaffold."""

from __future__ import annotations

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"
    nw_diff_api_token: Optional[str] = None
    nw_diff_basic_user: Optional[str] = None
    nw_diff_basic_password: Optional[str] = None
    nw_diff_basic_password_hash: Optional[str] = None
    device_password: Optional[str] = None
    db_url: str = "sqlite:///./nw_diff_v2.db"
    artifact_root: str = "./artifacts_v2"
    app_log_path: str = "./logs/nw-diff.log"
    hosts_csv: str = "hosts.csv"
    command_profiles_override_yaml: str = (
        "command_profiles/device_commands.override.yaml"
    )
    task_stream_sleep_seconds: float = 0.25
    task_stream_heartbeat_seconds: float = 10.0
    batch_conflict_policy: str = "all_or_nothing"
    host_lock_timeout_seconds: float = 3600.0
    task_worker_enabled: bool = True
    task_worker_threads: int = 1
    task_worker_poll_seconds: float = 0.5
    readiness_max_queued: int = 100
    readiness_max_running: int = 20
    readiness_max_locked: int = 100

    def validate_runtime(self) -> None:
        """Fail fast for invalid startup configuration."""
        if not self.device_password:
            raise RuntimeError("DEVICE_PASSWORD is required")

        is_dev = self.env.lower() in {"dev", "development", "local", "test"}
        if not is_dev and not self.nw_diff_api_token:
            raise RuntimeError(
                "NW_DIFF_API_TOKEN is required outside development environments"
            )


settings = Settings()
