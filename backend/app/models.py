"""
Data access layer: user, session, terminal session, IP ban, security event,
login attempt, and system setting helpers.

All functions are synchronous (blocking sqlite) and are invoked from async
endpoints via `database.run_db`, which offloads to a thread pool.
"""

from __future__ import annotations

import os
import time
from typing import Any, Optional

from .database import (
    execute,
    fetch_all,
    fetch_one,
    get_conn,
    last_insert_id,
    now_ts,
    transaction,
)

# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


def create_user(
    username: str,
    email: str,
    password_hash: str,
    role: str = "user",
) -> dict:
    with transaction() as conn:
        cur = execute(
            conn,
            "INSERT INTO users (username, email, password_hash, role, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (username, email, password_hash, role, now_ts()),
        )
        uid = last_insert_id(conn)
    return get_user_by_id(uid)


def get_user_by_id(user_id: int) -> Optional[dict]:
    with transaction() as conn:
        row = fetch_one(
            conn,
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        )
    return dict(row) if row else None


def get_user_by_username(username: str) -> Optional[dict]:
    with transaction() as conn:
        row = fetch_one(
            conn,
            "SELECT * FROM users WHERE username = ?",
            (username,),
        )
    return dict(row) if row else None


def get_user_by_email(email: str) -> Optional[dict]:
    with transaction() as conn:
        row = fetch_one(
            conn,
            "SELECT * FROM users WHERE email = ?",
            (email,),
        )
    return dict(row) if row else None


def list_users(
    search: Optional[str] = None,
    role: Optional[str] = None,
    is_active: Optional[int] = None,
    is_banned: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    sql = "SELECT id, username, email, role, is_active, is_banned, ban_reason, created_at, last_login FROM users"
    params: list[Any] = []
    clauses = []
    if search:
        clauses.append("(username LIKE ? OR email LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like])
    if role:
        clauses.append("role = ?")
        params.append(role)
    if is_active is not None:
        clauses.append("is_active = ?")
        params.append(is_active)
    if is_banned is not None:
        clauses.append("is_banned = ?")
        params.append(is_banned)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with transaction() as conn:
        rows = fetch_all(conn, sql, tuple(params))
    return [dict(r) for r in rows]


def count_users() -> int:
    with transaction() as conn:
        row = fetch_one(conn, "SELECT COUNT(*) AS c FROM users")
    return row["c"] if row else 0


def update_user(
    user_id: int,
    **fields,
) -> Optional[dict]:
    if not fields:
        return get_user_by_id(user_id)
    cols = ", ".join(f"{k} = ?" for k in fields)
    params = list(fields.values())
    params.append(user_id)
    with transaction() as conn:
        execute(
            conn,
            f"UPDATE users SET {cols} WHERE id = ?",
            tuple(params),
        )
    return get_user_by_id(user_id)


def set_user_resource_limits(
    user_id: int,
    ram_limit_mb: Optional[int] = None,
    cpu_limit: Optional[float] = None,
    disk_limit_mb: Optional[int] = None,
    pids_limit: Optional[int] = None,
    max_sessions: Optional[int] = None,
    max_session_duration_seconds: Optional[int] = None,
    idle_timeout_seconds: Optional[int] = None,
    max_command_time_seconds: Optional[int] = None,
) -> Optional[dict]:
    fields: dict[str, Any] = {}
    if ram_limit_mb is not None:
        fields["ram_limit_mb"] = ram_limit_mb
    if cpu_limit is not None:
        fields["cpu_limit"] = cpu_limit
    if disk_limit_mb is not None:
        fields["disk_limit_mb"] = disk_limit_mb
    if pids_limit is not None:
        fields["pids_limit"] = pids_limit
    if max_sessions is not None:
        fields["max_sessions"] = max_sessions
    if max_session_duration_seconds is not None:
        fields["max_session_duration_seconds"] = max_session_duration_seconds
    if idle_timeout_seconds is not None:
        fields["idle_timeout_seconds"] = idle_timeout_seconds
    if max_command_time_seconds is not None:
        fields["max_command_time_seconds"] = max_command_time_seconds
    return update_user(user_id, **fields)


def ban_user(user_id: int, reason: Optional[str], by_admin_id: Optional[int]) -> None:
    with transaction() as conn:
        execute(
            conn,
            "UPDATE users SET is_banned = 1, ban_reason = ? WHERE id = ?",
            (reason, user_id),
        )
        # Revoke all active sessions for the banned user.
        execute(
            conn,
            "UPDATE sessions SET is_active = 0 WHERE user_id = ? AND is_active = 1",
            (user_id,),
        )


def unban_user(user_id: int) -> None:
    with transaction() as conn:
        execute(
            conn,
            "UPDATE users SET is_banned = 0, ban_reason = NULL WHERE id = ?",
            (user_id,),
        )


def suspend_user(user_id: int) -> None:
    with transaction() as conn:
        execute(
            conn,
            "UPDATE users SET is_active = 0 WHERE id = ?",
            (user_id,),
        )
        execute(
            conn,
            "UPDATE sessions SET is_active = 0 WHERE user_id = ? AND is_active = 1",
            (user_id,),
        )


def unsuspend_user(user_id: int) -> None:
    with transaction() as conn:
        execute(
            conn,
            "UPDATE users SET is_active = 1 WHERE id = ?",
            (user_id,),
        )


def delete_user(user_id: int) -> None:
    with transaction() as conn:
        execute(conn, "DELETE FROM users WHERE id = ?", (user_id,))


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


def create_session(
    token: str,
    user_id: int,
    ip: Optional[str],
    user_agent: Optional[str],
    expires_at: int,
) -> None:
    with transaction() as conn:
        execute(
            conn,
            "INSERT INTO sessions (id, user_id, ip, user_agent, created_at, expires_at, last_activity, is_active) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
            (token, user_id, ip, user_agent, now_ts(), expires_at, now_ts()),
        )


def get_session(token: str) -> Optional[dict]:
    with transaction() as conn:
        row = fetch_one(
            conn,
            "SELECT * FROM sessions WHERE id = ?",
            (token,),
        )
    return dict(row) if row else None


def touch_session(token: str) -> None:
    with transaction() as conn:
        execute(
            conn,
            "UPDATE sessions SET last_activity = ? WHERE id = ?",
            (now_ts(), token),
        )


def revoke_session(token: str) -> None:
    with transaction() as conn:
        execute(
            conn,
            "UPDATE sessions SET is_active = 0 WHERE id = ?",
            (token,),
        )


def invalidate_user_sessions(user_id: int) -> None:
    with transaction() as conn:
        execute(
            conn,
            "UPDATE sessions SET is_active = 0 WHERE user_id = ? AND is_active = 1",
            (user_id,),
        )


# ---------------------------------------------------------------------------
# Terminal sessions
# ---------------------------------------------------------------------------


def create_terminal_session(
    session_id: str,
    user_id: int,
    container_name: Optional[str],
    exec_id: Optional[str],
    expires_at: Optional[int],
    command: str = "/bin/bash",
) -> None:
    with transaction() as conn:
        execute(
            conn,
            "INSERT INTO terminal_sessions "
            "(id, user_id, container_name, exec_id, status, created_at, last_activity, expires_at, command) "
            "VALUES (?, ?, ?, ?, 'running', ?, ?, ?, ?)",
            (session_id, user_id, container_name, exec_id, now_ts(), now_ts(), expires_at, command),
        )


def get_terminal_session(session_id: str) -> Optional[dict]:
    with transaction() as conn:
        row = fetch_one(
            conn,
            "SELECT * FROM terminal_sessions WHERE id = ?",
            (session_id,),
        )
    return dict(row) if row else None


def get_terminal_sessions_by_user(user_id: int) -> list[dict]:
    with transaction() as conn:
        rows = fetch_all(
            conn,
            "SELECT * FROM terminal_sessions WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        )
    return [dict(r) for r in rows]


def get_active_terminal_sessions() -> list[dict]:
    with transaction() as conn:
        rows = fetch_all(
            conn,
            "SELECT ts.*, u.username FROM terminal_sessions ts "
            "JOIN users u ON u.id = ts.user_id WHERE ts.status = 'running' "
            "ORDER BY ts.last_activity DESC",
        )
    return [dict(r) for r in rows]


def update_terminal_session(
    session_id: str,
    **fields,
) -> Optional[dict]:
    if not fields:
        return get_terminal_session(session_id)
    cols = ", ".join(f"{k} = ?" for k in fields)
    params = list(fields.values())
    params.append(session_id)
    with transaction() as conn:
        execute(
            conn,
            f"UPDATE terminal_sessions SET {cols} WHERE id = ?",
            tuple(params),
        )
    return get_terminal_session(session_id)


def set_terminal_session_status(session_id: str, status: str) -> None:
    with transaction() as conn:
        execute(
            conn,
            "UPDATE terminal_sessions SET status = ? WHERE id = ?",
            (status, session_id),
        )


def terminate_terminal_session(session_id: str) -> Optional[dict]:
    row = get_terminal_session(session_id)
    if row:
        with transaction() as conn:
            execute(
                conn,
                "UPDATE terminal_sessions SET status = 'stopped' WHERE id = ?",
                (session_id,),
            )
    return row


# ---------------------------------------------------------------------------
# IP bans
# ---------------------------------------------------------------------------


def is_ip_banned(ip: str) -> Optional[dict]:
    """Return the active ban row for an IP, or None if not banned."""
    with transaction() as conn:
        rows = fetch_all(
            conn,
            "SELECT * FROM ip_bans WHERE ip = ? AND is_active = 1",
            (ip,),
        )
    for r in rows:
        d = dict(r)
        if d["expires_at"] is None or d["expires_at"] >= now_ts():
            return d
    return None


def add_ip_ban(
    ip: str,
    reason: str,
    ban_type: str,
    banned_by: Optional[int],
    expires_at: Optional[int],
) -> int:
    with transaction() as conn:
        cur = execute(
            conn,
            "INSERT INTO ip_bans (ip, reason, ban_type, banned_by, banned_at, expires_at, is_active) "
            "VALUES (?, ?, ?, ?, ?, ?, 1)",
            (ip, reason, ban_type, banned_by, now_ts(), expires_at),
        )
        return last_insert_id(conn)


def remove_ip_ban(ip: str) -> None:
    with transaction() as conn:
        execute(
            conn,
            "UPDATE ip_bans SET is_active = 0 WHERE ip = ?",
            (ip,),
        )


def list_ip_bans(active_only: bool = True, limit: int = 100, offset: int = 0) -> list[dict]:
    sql = "SELECT * FROM ip_bans"
    params: list[Any] = []
    if active_only:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY banned_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with transaction() as conn:
        rows = fetch_all(conn, sql, tuple(params))
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Security events / audit log
# ---------------------------------------------------------------------------


def log_security_event(
    event_type: str,
    severity: str = "info",
    ip: Optional[str] = None,
    user_id: Optional[int] = None,
    details: Optional[str] = None,
) -> int:
    with transaction() as conn:
        cur = execute(
            conn,
            "INSERT INTO security_events (event_type, severity, ip, user_id, details, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (event_type, severity, ip, user_id, details, now_ts()),
        )
        return last_insert_id(conn)


def list_security_events(
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    sql = "SELECT * FROM security_events"
    params: list[Any] = []
    clauses = []
    if event_type:
        clauses.append("event_type = ?")
        params.append(event_type)
    if severity:
        clauses.append("severity = ?")
        params.append(severity)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with transaction() as conn:
        rows = fetch_all(conn, sql, tuple(params))
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Login attempts
# ---------------------------------------------------------------------------


def log_login_attempt(ip: Optional[str], username: str, success: bool) -> None:
    with transaction() as conn:
        execute(
            conn,
            "INSERT INTO login_attempts (ip, username, success, attempted_at) "
            "VALUES (?, ?, ?, ?)",
            (ip, username, 1 if success else 0, now_ts()),
        )


# ---------------------------------------------------------------------------
# System settings
# ---------------------------------------------------------------------------


def get_setting(key: str) -> Optional[str]:
    with transaction() as conn:
        row = fetch_one(
            conn,
            "SELECT value FROM system_settings WHERE key = ?",
            (key,),
        )
    return row["value"] if row else None


def set_setting(key: str, value: str, updated_by: Optional[int] = None) -> None:
    with transaction() as conn:
        execute(
            conn,
            "INSERT INTO system_settings (key, value, updated_at, updated_by) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at, updated_by = excluded.updated_by",
            (key, value, now_ts(), updated_by),
        )


def list_settings() -> dict[str, str]:
    with transaction() as conn:
        rows = fetch_all(conn, "SELECT key, value FROM system_settings")
    return {r["key"]: r["value"] for r in rows}


# ---------------------------------------------------------------------------
# Command history
# ---------------------------------------------------------------------------


def add_command_history(
    user_id: int,
    command: str,
    terminal_session_id: Optional[str] = None,
) -> None:
    with transaction() as conn:
        execute(
            conn,
            "INSERT INTO command_history (user_id, terminal_session_id, command, executed_at) "
            "VALUES (?, ?, ?, ?)",
            (user_id, terminal_session_id, command, now_ts()),
        )


def get_command_history(
    user_id: int,
    limit: int = 200,
    offset: int = 0,
) -> list[dict]:
    with transaction() as conn:
        rows = fetch_all(
            conn,
            "SELECT * FROM command_history WHERE user_id = ? ORDER BY executed_at DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset),
        )
    return [dict(r) for r in rows]
