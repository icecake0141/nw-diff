"""Minimal web UI endpoints for v2."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from nw_diff_v2.config import settings
from nw_diff_v2.infra.repositories.host_repo import load_hosts

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))

router = APIRouter(tags=["v2-ui"])


@router.get("/v2", response_class=HTMLResponse)
def v2_index(request: Request) -> HTMLResponse:
    """Render minimal v2 control panel."""
    hosts = load_hosts(settings.hosts_csv)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "hosts": [row.model_dump() for row in hosts],
        },
    )


@router.get("/v2/hosts/{hostname}", response_class=HTMLResponse)
def v2_host_detail(request: Request, hostname: str) -> HTMLResponse:
    """Render host detail page shell; data is fetched from API."""
    return templates.TemplateResponse(
        request,
        "host_detail.html",
        {
            "hostname": hostname,
        },
    )


@router.get("/v2/logs", response_class=HTMLResponse)
def v2_logs_page(request: Request) -> HTMLResponse:
    """Render logs UI shell."""
    return templates.TemplateResponse(
        request,
        "logs.html",
        {},
    )
