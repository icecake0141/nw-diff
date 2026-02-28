"""Standalone queue worker entrypoint for v2."""

from __future__ import annotations

import logging
import signal
import threading
import time

from nw_diff_v2.config import settings
from nw_diff_v2.domain.services.lock_service import cleanup_stale_locks, release_hosts
from nw_diff_v2.domain.services.task_worker import process_one_queued_task
from nw_diff_v2.infra.repositories.task_repo import (
    init_db,
    recover_orphaned_running_tasks,
)

logger = logging.getLogger("nw-diff-v2-worker")


def run_forever() -> None:
    """Run queue worker loop until interrupted."""
    settings.validate_runtime()
    init_db()
    deleted_locks = cleanup_stale_locks()
    if deleted_locks:
        logger.warning("cleaned up %d stale lock(s) at startup", deleted_locks)
    recovered = recover_orphaned_running_tasks()
    for task in recovered:
        release_hosts(set(task["hosts"]))
    if recovered:
        logger.warning("recovered %d orphaned running task(s)", len(recovered))

    stop_event = threading.Event()

    def _handle_signal(signum, _frame):  # noqa: ANN001
        logger.info("received signal %s, shutting down worker", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    logger.info("worker started")
    while not stop_event.is_set():
        processed = process_one_queued_task()
        if processed:
            continue
        stop_event.wait(max(0.05, settings.task_worker_poll_seconds))
    logger.info("worker stopped")


if __name__ == "__main__":
    run_forever()
