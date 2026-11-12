"""
Admin user management routes.

All endpoints require the admin role and enforce permissions on the backend.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel

from ..auth import CSRF_COOKIE, get_current_user, hash_password, require_admin, verify_csrf
from ..database import run_db
from ..logging import get_logger
from ..models import (
    add_command_history,
    ban_user,
    count_users,
    create_user,
    delete_user,
    get_active_terminal_sessions,
    get_command_history,
    get_setting,
    get_terminal_session,
    get_terminal_sessions_by_user,
    get_user_by_id,
    get_user_by_username,
    list_security_events,
    list_users,
    log_security_event,
    set_user_resource_limits,
    suspend_user,
    terminate_terminal_session,
    unban_user,
    unsuspend_user,
    update_user,
)
from ..security import enforce_ip_ban, get_client_ip

router = APIRouter()
logger = get_logger(__name__)


class UserListResponse(BaseModel):
    users: list[dict]
    total: int


class UserUpdateRequest(BaseModel):
    is_active: Optional[bool] = None
    role: Optional[str] = None


class ResourceLimitsRequest(BaseModel):
    ram_limit_mb: Optional[int] = None
    cpu_limit: Optional[float] = None
    disk_limit_mb: Optional[int] = None
    pids_limit: Optional[int] = None
    max_sessions: Optional[int] = None
    max_session_duration_seconds: Optional[int] = None
    idle_timeout_seconds: Optional[int] = None
    max_command_time_seconds: Optional[int] = None


# ---------------------------------------------------------------------------
# Overview / stats
# ---------------------------------------------------------------------------

@router.get("/overview")
async def admin_overview(_admin=Depends(require_admin)):
    total = await run_db(count_users)
    active_sessions = await run_db(get_active_terminal_sessions)
    return {
        "total_users": total,
        "active_sessions": len(active_sessions),
        "max_concurrent_users": int(get_setting("max_concurrent_users") or "2000"),
        "registration_enabled": get_setting("registration_enabled") != "disabled",
        "maintenance_mode": get_setting("maintenance_mode") == "enabled",
    }

@router.get("/terminals")
async def admin_list_terminals(_admin=Depends(require_admin)):
    sessions = await run_db(get_active_terminal_sessions)
    return {
        "terminals": [
            {
                "id": s["id"],
                "user_id": s["user_id"],
                "username": s["username"],
                "container_name": s["container_name"],
                "exec_id": s["exec_id"],
                "created_at": s["created_at"],
                "last_activity": s["last_activity"],
                "cols": s["cols"],
                "rows": s["rows"],
            }
            for s in sessions
        ]
    }
    total = await run_db(count_users)
    active_sessions = await run_db(get_active_terminal_sessions)
    return {
        "total_users": total,
        "active_sessions": len(active_sessions),
        "max_concurrent_users": int(get_setting("max_concurrent_users") or "2000"),
        "registration_enabled": get_setting("registration_enabled") != "disabled",
        "maintenance_mode": get_setting("maintenance_mode") == "enabled",
    }


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

@router.get("/users", response_model=UserListResponse)
async def admin_list_users(
    request: Request,
    _admin=Depends(require_admin),
    search: Optional[str] = Query(default=None),
    role: Optional[str] = Query(default=None),
    is_active: Optional[int] = Query(default=None),
    is_banned: Optional[int] = Query(default=None),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
):
    ip = get_client_ip(request)
    users = await run_db(
        list_users, search, role, is_active, is_banned, limit, offset
    )
    await run_db(
        log_security_event,
        "admin_list_users",
        "info",
        ip,
        _admin["user_id"],
        f"Admin {_admin['username']} listed users",
    )
    return {"users": users, "total": len(users)}


@router.get("/users/{user_id}")
async def admin_get_user(user_id: int, _admin=Depends(require_admin)):
    user = await run_db(get_user_by_id, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # Hide password hash.
    user.pop("password_hash", None)
    sessions = await run_db(get_terminal_sessions_by_user, user_id)
    return {"user": user, "sessions": sessions}


@router.post("/users/{user_id}/suspend")
async def admin_suspend_user(
    user_id: int,
    request: Request,
    _admin=Depends(require_admin),
    csrf_cookie: Optional[str] = Cookie(default=None, alias=CSRF_COOKIE),
    csrf_header: Optional[str] = Header(default=None, alias="x-csrf-token"),
):
    verify_csrf(request, csrf_cookie, csrf_header)
    ip = get_client_ip(request)
    target = await run_db(get_user_by_id, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    await run_db(suspend_user, user_id)
    await run_db(
        log_security_event,
        "admin_suspend_user",
        "warning",
        ip,
        _admin["user_id"],
        f"Admin {_admin['username']} suspended user {target['username']}",
    )
    return {"message": f"User {target['username']} suspended."}


@router.post("/users/{user_id}/unsuspend")
async def admin_unsuspend_user(
    user_id: int,
    request: Request,
    _admin=Depends(require_admin),
    csrf_cookie: Optional[str] = Cookie(default=None, alias=CSRF_COOKIE),
    csrf_header: Optional[str] = Header(default=None, alias="x-csrf-token"),
):
    verify_csrf(request, csrf_cookie, csrf_header)
    ip = get_client_ip(request)
    target = await run_db(get_user_by_id, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    await run_db(unsuspend_user, user_id)
    await run_db(
        log_security_event,
        "admin_unsuspend_user",
        "info",
        ip,
        _admin["user_id"],
        f"Admin {_admin['username']} unsuspended user {target['username']}",
    )
    return {"message": f"User {target['username']} unsuspended."}


@router.post("/users/{user_id}/ban")
async def admin_ban_user(
    user_id: int,
    request: Request,
    _admin=Depends(require_admin),
    csrf_cookie: Optional[str] = Cookie(default=None, alias=CSRF_COOKIE),
    csrf_header: Optional[str] = Header(default=None, alias="x-csrf-token"),
    reason: Optional[str] = None,
):
    verify_csrf(request, csrf_cookie, csrf_header)
    ip = get_client_ip(request)
    target = await run_db(get_user_by_id, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    await run_db(ban_user, user_id, reason, _admin["user_id"])
    await run_db(
        log_security_event,
        "admin_ban_user",
        "warning",
        ip,
        _admin["user_id"],
        f"Admin {_admin['username']} banned user {target['username']}: {reason or 'no reason'}",
    )
    return {"message": f"User {target['username']} banned."}


@router.post("/users/{user_id}/unban")
async def admin_unban_user(
    user_id: int,
    request: Request,
    _admin=Depends(require_admin),
    csrf_cookie: Optional[str] = Cookie(default=None, alias=CSRF_COOKIE),
    csrf_header: Optional[str] = Header(default=None, alias="x-csrf-token"),
):
    verify_csrf(request, csrf_cookie, csrf_header)
    ip = get_client_ip(request)
    target = await run_db(get_user_by_id, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    await run_db(unban_user, user_id)
    await run_db(
        log_security_event,
        "admin_unban_user",
        "info",
        ip,
        _admin["user_id"],
        f"Admin {_admin['username']} unbanned user {target['username']}",
    )
    return {"message": f"User {target['username']} unbanned."}


@router.post("/users/{user_id}/sessions/{session_id}/terminate")
async def admin_terminate_session(
    user_id: int,
    session_id: str,
    request: Request,
    _admin=Depends(require_admin),
    csrf_cookie: Optional[str] = Cookie(default=None, alias=CSRF_COOKIE),
    csrf_header: Optional[str] = Header(default=None, alias="x-csrf-token"),
):
    verify_csrf(request, csrf_cookie, csrf_header)
    ip = get_client_ip(request)
    row = await run_db(get_terminal_session, session_id)
    if not row or row["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Session not found")
    await run_db(terminate_terminal_session, session_id)
    await run_db(
        log_security_event,
        "admin_terminate_session",
        "warning",
        ip,
        _admin["user_id"],
        f"Admin {_admin['username']} terminated terminal session {session_id}",
    )
    return {"message": "Session terminated."}


@router.put("/users/{user_id}/resource-limits")
async def admin_set_resource_limits(
    user_id: int,
    payload: ResourceLimitsRequest,
    request: Request,
    _admin=Depends(require_admin),
    csrf_cookie: Optional[str] = Cookie(default=None, alias=CSRF_COOKIE),
    csrf_header: Optional[str] = Header(default=None, alias="x-csrf-token"),
):
    verify_csrf(request, csrf_cookie, csrf_header)
    ip = get_client_ip(request)
    target = await run_db(get_user_by_id, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    updated = await run_db(
        set_user_resource_limits,
        user_id,
        ram_limit_mb=payload.ram_limit_mb,
        cpu_limit=payload.cpu_limit,
        disk_limit_mb=payload.disk_limit_mb,
        pids_limit=payload.pids_limit,
        max_sessions=payload.max_sessions,
        max_session_duration_seconds=payload.max_session_duration_seconds,
        idle_timeout_seconds=payload.idle_timeout_seconds,
        max_command_time_seconds=payload.max_command_time_seconds,
    )
    await run_db(
        log_security_event,
        "admin_set_resource_limits",
        "info",
        ip,
        _admin["user_id"],
        f"Admin {_admin['username']} set resource limits for user {target['username']}",
    )
    updated.pop("password_hash", None)
    return {"message": "Resource limits updated.", "user": updated}


@router.get("/users/{user_id}/history")
async def admin_user_history(
    user_id: int,
    _admin=Depends(require_admin),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
):
    history = await run_db(get_command_history, user_id, limit, offset)
    return {"history": history}
