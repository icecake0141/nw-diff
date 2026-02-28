"""FastAPI entrypoint for the v2 scaffold."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from nw_diff_v2.api.capture import router as capture_router
from nw_diff_v2.api.compare import router as compare_router
from nw_diff_v2.api.exports import router as exports_router
from nw_diff_v2.api.hosts import router as hosts_router
from nw_diff_v2.api.logs import router as logs_router
from nw_diff_v2.api.system import router as system_router
from nw_diff_v2.api.tasks import router as tasks_router
from nw_diff_v2.api.ui import router as ui_router
from nw_diff_v2.domain.services.lock_service import cleanup_stale_locks, release_hosts
from nw_diff_v2.domain.services.task_worker import TaskWorkerManager
from nw_diff_v2.infra.repositories.task_repo import init_db, recover_orphaned_running_tasks

_worker_manager = TaskWorkerManager()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Validate runtime configuration at startup."""
    from nw_diff_v2.config import settings

    settings.validate_runtime()
    init_db()
    cleanup_stale_locks()
    recovered = recover_orphaned_running_tasks()
    for task in recovered:
        release_hosts(set(task["hosts"]))
    if settings.task_worker_enabled:
        _worker_manager.start()
    yield
    _worker_manager.stop()


app = FastAPI(title="NW-Diff v2 Scaffold", lifespan=lifespan)
app.include_router(capture_router)
app.include_router(compare_router)
app.include_router(hosts_router)
app.include_router(logs_router)
app.include_router(tasks_router)
app.include_router(exports_router)
app.include_router(ui_router)
app.include_router(system_router)
