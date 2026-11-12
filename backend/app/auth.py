"""
Authentication and authorization.

- Passwords are hashed with bcrypt (never plaintext).
- Server-side sessions stored in SQLite, issued as an HttpOnly Secure SameSite=Strict cookie.
- Short-lived JWTs are used as WebSocket upgrade tokens (query-param fallback).
- Role-based access: 'admin' or 'user'. All enforcement happens on the backend.
"""

from __future__ import annotations

import os
import secrets
import time
from typing import Any, Optional

import bcrypt
import jwt
from fastapi import Cookie, Depends, Header, HTTPException, Query, Request, WebSocket, status
from fastapi.security import OAuth2PasswordBearer

from .database import now_ts, run_db, transaction
from .logging import get_logger
from .models import (
    create_session,
    get_session,
    get_user_by_id,
    get_user_by_username,
    invalidate_user_sessions,
    revoke_session,
    touch_session,
)

logger = get_logger(__name__)

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-to-a-strong-random-secret")
SESSION_TTL = int(os.getenv("SESSION_TTL_SECONDS", "86400"))
WS_TOKEN_TTL = int(os.getenv("WS_TOKEN_TTL_SECONDS", "900"))

SESSION_COOKIE = "session_id"
CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "x-csrf-token"

# OAuth2 bearer scheme (kept for optional API clients; cookie is primary).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT helpers (WebSocket upgrade tokens only)
# ---------------------------------------------------------------------------

def create_ws_token(user_id: int) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + WS_TOKEN_TTL,
        "purpose": "ws-upgrade",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def decode_ws_token(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        if payload.get("purpose") != "ws-upgrade":
            return None
        return int(payload["sub"])
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

async def create_auth_session(
    user_id: int,
    ip: Optional[str],
    user_agent: Optional[str],
) -> str:
    token = secrets.token_urlsafe(32)
    await run_db(
        create_session,
        token,
        user_id,
        ip,
        user_agent,
        now_ts() + SESSION_TTL,
    )
    return token


async def get_current_session(
    request: Request,
) -> Optional[dict[str, Any]]:
    """Resolve the authenticated session from the cookie.

    Returns the session row dict or None. Does not raise (endpoints decide).
    """
    session_id = request.cookies.get(SESSION_COOKIE)
    if not session_id:
        return None
    row = await run_db(get_session, session_id)
    if row is None:
        return None
    if row["is_active"] == 0 or row["expires_at"] < now_ts():
        await run_db(revoke_session, session_id)
        return None
    user = await run_db(get_user_by_id, row["user_id"])
    if user is None or user["is_active"] == 0:
        await run_db(revoke_session, session_id)
        return None
    if user["is_banned"] == 1:
        await run_db(revoke_session, session_id)
        return None
    await run_db(touch_session, session_id)
    return {
        "session_id": session_id,
        "user_id": row["user_id"],
        "role": user["role"],
        "username": user["username"],
        "email": user["email"],
        "is_admin": user["role"] == "admin",
        "ip": row["ip"],
    }


async def get_current_user(request: Request) -> dict[str, Any]:
    """Dependency for endpoints that require authentication. Raises 401."""
    session = await get_current_session(request)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    request.state.user = session
    return session


async def require_admin(request: Request) -> dict[str, Any]:
    """Dependency for admin-only endpoints. Raises 403 for non-admins."""
    session = await get_current_user(request)
    if not session["is_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to perform this action.",
        )
    request.state.user = session
    return session


async def require_user(request: Request) -> dict[str, Any]:
    """Dependency for any authenticated user."""
    return await get_current_user(request)


# ---------------------------------------------------------------------------
# WebSocket authentication
# ---------------------------------------------------------------------------

async def authenticate_websocket(
    websocket: WebSocket,
    token: Optional[str] = Query(default=None),
    session_id: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, Any]:
    """Authenticate a WebSocket connection.

    Preference order: session cookie, then short-lived WS upgrade token.
    The cookie is preferred because browsers send it automatically; the query
    token is a fallback for clients that cannot set cookies. Tokens are
    short-lived and single-purpose (ws-upgrade).
    """
    # 1) Session cookie (preferred)
    if session_id:
        row = await run_db(get_session, session_id)
        if row and row["is_active"] == 1 and row["expires_at"] >= now_ts():
            user = await run_db(get_user_by_id, row["user_id"])
            if (
                user
                and user["is_active"] == 1
                and user["is_banned"] == 0
            ):
                await run_db(touch_session, session_id)
                return {
                    "session_id": session_id,
                    "user_id": row["user_id"],
                    "role": user["role"],
                    "username": user["username"],
                    "email": user["email"],
                    "is_admin": user["role"] == "admin",
                    "ip": row["ip"],
                }

    # 2) Short-lived JWT upgrade token
    if token:
        user_id = decode_ws_token(token)
        if user_id is not None:
            user = await run_db(get_user_by_id, user_id)
            if user and user["is_active"] == 1 and user["is_banned"] == 0:
                return {
                    "session_id": None,
                    "user_id": user["id"],
                    "role": user["role"],
                    "username": user["username"],
                    "email": user["email"],
                    "is_admin": user["role"] == "admin",
                    "ip": None,
                }

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )


# ---------------------------------------------------------------------------
# CSRF
# ---------------------------------------------------------------------------

def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def verify_csrf(
    request: Request,
    csrf_cookie: Optional[str] = Cookie(default=None, alias=CSRF_COOKIE),
    csrf_header: Optional[str] = Header(default=None, alias=CSRF_HEADER),
) -> None:
    """Double-submit CSRF verification for state-changing requests.

    Requires the X-CSRF-Token header to match the csrf_token cookie. Safe
    methods (GET/HEAD/OPTIONS) are exempt.
    """
    if request.method in ("GET", "HEAD", "OPTIONS", "TRACE"):
        return
    if not csrf_cookie or not csrf_header:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing",
        )
    if not secrets.compare_digest(csrf_cookie, csrf_header):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token mismatch",
        )


__all__ = [
    "hash_password",
    "verify_password",
    "create_ws_token",
    "decode_ws_token",
    "create_auth_session",
    "get_current_session",
    "get_current_user",
    "require_admin",
    "require_user",
    "authenticate_websocket",
    "generate_csrf_token",
    "verify_csrf",
    "SESSION_COOKIE",
    "CSRF_COOKIE",
]
