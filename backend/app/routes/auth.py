"""
Authentication routes: register, login, logout, me, csrf token.

All enforcement happens on the backend. Passwords are hashed with bcrypt;
sessions are server-side SQLite rows issued as an HttpOnly Secure SameSite=Strict cookie.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Cookie, Header, Request, Response, status
from fastapi import Depends
from pydantic import BaseModel, EmailStr, Field

from ..auth import (
    SESSION_COOKIE,
    CSRF_COOKIE,
    create_auth_session,
    create_ws_token,
    generate_csrf_token,
    get_current_session,
    get_current_user,
    hash_password,
    verify_csrf,
    verify_password,
)
from ..database import run_db
from ..logging import get_logger
from ..models import (
    create_user,
    get_setting,
    get_user_by_email,
    get_user_by_username,
    log_security_event,
    revoke_session,
)
from ..security import (
    check_login_rate,
    check_register_rate,
    enforce_ip_ban,
    get_client_ip,
    record_login_attempt,
)

router = APIRouter()
logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class MeResponse(BaseModel):
    user_id: int
    username: str
    email: str
    role: str
    is_admin: bool


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/csrf")
async def csrf_token(response: Response):
    """Issue a CSRF token value and set it as a (non-HttpOnly) cookie.

    The frontend reads the cookie and echoes it back as the
    X-CSRF-Token header on state-changing requests (double-submit pattern).
    """
    token = generate_csrf_token()
    response.set_cookie(
        key=CSRF_COOKIE,
        value=token,
        httponly=False,
        secure=True,
        samesite="strict",
        path="/",
        max_age=86400,
    )
    return {"csrf_token": token}


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    request: Request,
    response: Response,
    payload: RegisterRequest,
    csrf_cookie: Optional[str] = Cookie(default=None, alias=CSRF_COOKIE),
    csrf_header: Optional[str] = Header(default=None, alias="x-csrf-token"),
):
    ip = get_client_ip(request)

    # IP ban check.
    ban = await enforce_ip_ban(ip)
    if ban:
        await run_db(
            log_security_event,
            "registration_blocked_banned_ip",
            "warning",
            ip,
            None,
            f"Attempted registration from banned IP {ip}",
        )
        return Response(
            content="You are not allowed to perform this action.",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    # Rate limit.
    if not check_register_rate(ip):
        await run_db(
            log_security_event,
            "registration_rate_limited",
            "warning",
            ip,
            None,
            f"Registration rate limit exceeded from IP {ip}",
        )
        return Response(
            content="Too many registration attempts. Try again later.",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    # CSRF.
    verify_csrf(request, csrf_cookie, csrf_header)

    # Registration enabled?
    if get_setting("registration_enabled") == "disabled":
        return Response(
            content="New user registration is currently disabled.",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    # Duplicate checks.
    if get_user_by_username(payload.username):
        return Response(
            content="Username already taken.",
            status_code=status.HTTP_409_CONFLICT,
        )
    if get_user_by_email(payload.email):
        return Response(
            content="Email already registered.",
            status_code=status.HTTP_409_CONFLICT,
        )

    # Create user (default role 'user').
    create_user(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role="user",
    )
    await run_db(
        log_security_event,
        "user_registered",
        "info",
        ip,
        None,
        f"New user registered: {payload.username}",
    )
    return {"message": "Registration successful. Please log in."}


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    csrf_cookie: Optional[str] = Cookie(default=None, alias=CSRF_COOKIE),
    csrf_header: Optional[str] = Header(default=None, alias="x-csrf-token"),
):
    ip = get_client_ip(request)

    # IP ban check.
    ban = await enforce_ip_ban(ip)
    if ban:
        record_login_attempt(ip, payload.username, False)
        await run_db(
            log_security_event,
            "login_blocked_banned_ip",
            "warning",
            ip,
            None,
            f"Login attempt from banned IP {ip} for user {payload.username}",
        )
        return Response(
            content="You are not allowed to perform this action.",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    # Rate limit.
    if not check_login_rate(ip):
        record_login_attempt(ip, payload.username, False)
        await run_db(
            log_security_event,
            "login_rate_limited",
            "warning",
            ip,
            None,
            f"Login rate limit exceeded from IP {ip}",
        )
        return Response(
            content="Too many login attempts. Try again later.",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    # CSRF.
    verify_csrf(request, csrf_cookie, csrf_header)

    user = get_user_by_username(payload.username) or get_user_by_email(payload.username)

    if not user or not verify_password(payload.password, user["password_hash"]):
        record_login_attempt(ip, payload.username, False)
        await run_db(
            log_security_event,
            "login_failed",
            "warning",
            ip,
            user["id"] if user else None,
            f"Failed login for {payload.username}",
        )
        return Response(
            content="Invalid credentials.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if user["is_active"] == 0:
        record_login_attempt(ip, payload.username, False)
        await run_db(
            log_security_event,
            "login_suspended_user",
            "warning",
            ip,
            user["id"],
            f"Login attempt by suspended user {payload.username}",
        )
        return Response(
            content="Your account is suspended.",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    if user["is_banned"] == 1:
        record_login_attempt(ip, payload.username, False)
        await run_db(
            log_security_event,
            "login_banned_user",
            "warning",
            ip,
            user["id"],
            f"Login attempt by banned user {payload.username}",
        )
        return Response(
            content="Your account is banned.",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    # Success: create server-side session.
    user_agent = request.headers.get("user-agent")
    token = await create_auth_session(user["id"], ip, user_agent)
    record_login_attempt(ip, payload.username, True)
    await run_db(
        log_security_event,
        "login_success",
        "info",
        ip,
        user["id"],
        f"Successful login for {payload.username}",
    )

    # CSRF token cookie (non-HttpOnly so JS can echo it as a header).
    csrf_token = generate_csrf_token()
    response.set_cookie(
        key=CSRF_COOKIE,
        value=csrf_token,
        httponly=False,
        secure=True,
        samesite="strict",
        path="/",
        max_age=86400,
    )

    # Session cookie (HttpOnly).
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
        max_age=int(__import__("os").getenv("SESSION_TTL_SECONDS", "86400")),
    )

    # Short-lived WS upgrade token for clients that cannot rely on cookies.
    ws_token = create_ws_token(user["id"])

    return {
        "message": "Login successful.",
        "user": {
            "user_id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "role": user["role"],
            "is_admin": user["role"] == "admin",
        },
        "ws_token": ws_token,
    }


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    session_id: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
):
    session = await get_current_session(request)
    if session:
        await run_db(revoke_session, session["session_id"])
        await run_db(
            log_security_event,
            "logout",
            "info",
            None,
            session["user_id"],
            f"User {session['username']} logged out",
        )

    response.delete_cookie(key=SESSION_COOKIE, path="/")
    response.delete_cookie(key=CSRF_COOKIE, path="/")
    return {"message": "Logged out."}


@router.get("/me", response_model=MeResponse)
async def me(user=Depends(get_current_user)):
    return MeResponse(
        user_id=user["user_id"],
        username=user["username"],
        email=user["email"],
        role=user["role"],
        is_admin=user["is_admin"],
    )
