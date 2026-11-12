"""
Security management routes: IP bans, audit log, system settings.

All endpoints require the admin role. Enforcement happens on the backend.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel

from ..auth import CSRF_COOKIE, require_admin, verify_csrf
from ..database import run_db
from ..logging import get_logger
from ..models import (
    add_ip_ban,
    get_setting,
    list_ip_bans,
    list_security_events,
    log_security_event,
    remove_ip_ban,
    set_setting,
)
from ..security import (
    enforce_ip_ban,
    get_client_ip,
    is_ip_banned,
)

router = APIRouter()
logger = get_logger(__name__)


class IpBanRequest(BaseModel):
    ip: str
    reason: str
    ban_type: str = "permanent"  # 'permanent' or 'temporary'
    expires_at: Optional[int] = None


class SettingRequest(BaseModel):
    key: str
    value: str


# ---------------------------------------------------------------------------
# IP bans
# ---------------------------------------------------------------------------

@router.get("/ip-bans")
async def list_ip_bans_endpoint(
    _admin=Depends(require_admin),
    active_only: bool = Query(default=True),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
):
    bans = await run_db(list_ip_bans, active_only, limit, offset)
    return {"bans": bans}


@router.post("/ip-bans", status_code=status.HTTP_201_CREATED)
async def create_ip_ban(
    request: Request,
    payload: IpBanRequest,
    _admin=Depends(require_admin),
    csrf_cookie: Optional[str] = Cookie(default=None, alias=CSRF_COOKIE),
    csrf_header: Optional[str] = Header(default=None, alias="x-csrf-token"),
):
    verify_csrf(request, csrf_cookie, csrf_header)
    ip = get_client_ip(request)

    if payload.ban_type not in ("permanent", "temporary"):
        raise HTTPException(status_code=400, detail="ban_type must be 'permanent' or 'temporary'")
    if payload.ban_type == "temporary" and not payload.expires_at:
        raise HTTPException(status_code=400, detail="expires_at required for temporary bans")

    ban_id = await run_db(
        add_ip_ban,
        payload.ip,
        payload.reason,
        payload.ban_type,
        _admin["user_id"],
        payload.expires_at,
    )
    await run_db(
        log_security_event,
        "admin_add_ip_ban",
        "warning",
        ip,
        _admin["user_id"],
        f"Admin {_admin['username']} banned IP {payload.ip}: {payload.reason}",
    )
    return {"message": "IP banned.", "ban_id": ban_id}


@router.delete("/ip-bans/{ip}")
async def delete_ip_ban(
    ip: str,
    request: Request,
    _admin=Depends(require_admin),
    csrf_cookie: Optional[str] = Cookie(default=None, alias=CSRF_COOKIE),
    csrf_header: Optional[str] = Header(default=None, alias="x-csrf-token"),
):
    verify_csrf(request, csrf_cookie, csrf_header)
    admin_ip = get_client_ip(request)
    await run_db(remove_ip_ban, ip)
    await run_db(
        log_security_event,
        "admin_remove_ip_ban",
        "info",
        admin_ip,
        _admin["user_id"],
        f"Admin {_admin['username']} removed ban for IP {ip}",
    )
    return {"message": f"Ban removed for IP {ip}."}


@router.get("/ip-bans/check/{ip}")
async def check_ip_ban(ip: str, _admin=Depends(require_admin)):
    ban = await run_db(is_ip_banned, ip)
    return {"ip": ip, "banned": ban is not None, "ban": ban}


# ---------------------------------------------------------------------------
# Security / audit events
# ---------------------------------------------------------------------------

@router.get("/events")
async def security_events(
    _admin=Depends(require_admin),
    event_type: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
):
    events = await run_db(list_security_events, event_type, severity, limit, offset)
    return {"events": events}


# ---------------------------------------------------------------------------
# System settings
# ---------------------------------------------------------------------------

@router.get("/settings")
async def list_settings(_admin=Depends(require_admin)):
    from ..models import list_settings as _ls

    return _ls()


@router.post("/settings")
async def update_setting(
    request: Request,
    payload: SettingRequest,
    _admin=Depends(require_admin),
    csrf_cookie: Optional[str] = Cookie(default=None, alias=CSRF_COOKIE),
    csrf_header: Optional[str] = Header(default=None, alias="x-csrf-token"),
):
    verify_csrf(request, csrf_cookie, csrf_header)
    admin_ip = get_client_ip(request)
    await run_db(set_setting, payload.key, payload.value, _admin["user_id"])
    await run_db(
        log_security_event,
        "admin_update_setting",
        "info",
        admin_ip,
        _admin["user_id"],
        f"Admin {_admin['username']} set setting {payload.key}",
    )
    return {"message": "Setting updated."}
