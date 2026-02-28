"""Background worker for queued v2 capture tasks."""

from __future__ import annotations

import threading
import time

from nw_diff_v2.config import settings
from nw_diff_v2.domain.models import CaptureBase, CaptureTaskStatus
from nw_diff_v2.domain.services.capture_service import run_capture_task
from nw_diff_v2.domain.services.lock_service import release_hosts
from nw_diff_v2.infra.repositories.host_repo import load_hosts
from nw_diff_v2.infra.repositories.task_repo import claim_next_queued_task, update_task
from nw_diff_v2.infra.storage.task_logs import append_task_log


def process_one_queued_task() -> bool:
    """Claim and process one queued task. Returns True when a task was processed."""
    task = claim_next_queued_task()
    if task is None:
        return False

    task_id = task["task_id"]
    base = CaptureBase(task["base"])
    hosts = list(task["hosts"])
    reserved_hosts = set(hosts)

    host_rows = load_hosts(settings.hosts_csv)
    host_map = {row.host: row.model_dump() for row in host_rows}
    missing_hosts = sorted(set(hosts).difference(host_map.keys()))
    if missing_hosts:
        message = f"Host definitions not found: {', '.join(missing_hosts)}"
        append_task_log(task_id, message)
        update_task(
            task_id,
            status=CaptureTaskStatus.FAILED,
            finished_at=time.time(),
            error=message,
        )
        release_hosts(reserved_hosts)
        return True

    ordered_host_rows = [host_map[host] for host in hosts]
    run_capture_task(
        task_id=task_id,
        base=base,
        hosts=ordered_host_rows,
        reserved_hosts=reserved_hosts,
    )
    return True


class TaskWorkerManager:
    """Process-local queue workers."""

    def __init__(self) -> None:
        self._threads: list[threading.Thread] = []
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._threads:
            return

        workers = max(1, int(settings.task_worker_threads))
        for idx in range(workers):
            thread = threading.Thread(
                target=self._worker_loop,
                kwargs={"worker_name": f"v2-worker-{idx + 1}"},
                daemon=True,
            )
            thread.start()
            self._threads.append(thread)

    def stop(self, timeout: float = 2.0) -> None:
        self._stop_event.set()
        deadline = time.time() + max(0.1, timeout)
        for thread in self._threads:
            remaining = max(0.0, deadline - time.time())
            thread.join(timeout=remaining)
        self._threads.clear()

    def _worker_loop(self, *, worker_name: str) -> None:
        while not self._stop_event.is_set():
            processed = process_one_queued_task()
            if processed:
                continue
            self._stop_event.wait(max(0.05, settings.task_worker_poll_seconds))
