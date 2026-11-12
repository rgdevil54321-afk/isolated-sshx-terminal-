"""
FastAPI application for the Multi-User Isolated Web Terminal Platform.

Routes:
  - /api/auth/*        - register, login, logout, me, csrf
  - /api/terminal/*    - terminal sessions + WebSocket proxy
  - /api/admin/users/* - admin user management
  - /api/admin/security/* - IP bans, audit, settings
  - /api/health, /api/ready
"""

from __future__ import annotations

import os
import time
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .auth import SESSION_COOKIE, get_current_session
from .container import container_manager
from .database import init_db, now_ts
from .logging import get_logger
from .models import get_setting, set_setting, log_security_event
from .routes import auth as auth_routes
from .routes import security as security_routes
from .routes import terminal as terminal_routes
from .routes import users as users_routes
from .security import get_client_ip

logger = get_logger(__name__)

app = FastAPI(
    title="Multi-User Isolated Web Terminal",
    description="Secure, isolated terminal platform for community VPS drops.",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

cors_origins = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins if cors_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Trusted-proxy / request-id / audit middleware
# ---------------------------------------------------------------------------

@app.middleware("http")
async def request_middleware(request: Request, call_next):
    start = time.time()
    request_id = os.urandom(8).hex()
    request.state.request_id = request_id

    # Resolve real client IP via trusted proxy only.
    request.state.client_ip = get_client_ip(request)

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ---------------------------------------------------------------------------
# Startup / shutdown
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def on_startup():
    init_db()
    # Bootstrap default settings if absent.
    defaults = {
        "registration_enabled": "enabled",
        "maintenance_mode": "disabled",
        "max_concurrent_users": "2000",
        "max_sessions_per_user": "2",
        "max_session_duration_seconds": "28800",
        "idle_timeout_seconds": "1800",
        "max_command_time_seconds": "120",
    }
    for key, value in defaults.items():
        if get_setting(key) is None:
            set_setting(key, value)

    # Bootstrap admin account if configured.
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    if admin_email and admin_password:
        from .models import get_user_by_email, create_user
        from .auth import hash_password

        if not get_user_by_email(admin_email):
            create_user(
                username=admin_username,
                email=admin_email,
                password_hash=hash_password(admin_password),
                role="admin",
            )
            logger.info("Bootstrapped admin account: %s", admin_email)
        else:
            # Ensure role is admin.
            from .models import update_user

            u = get_user_by_email(admin_email)
            if u["role"] != "admin":
                update_user(u["id"], role="admin")

    logger.info("Terminal platform started.")


@app.on_event("shutdown")
async def on_shutdown():
    container_manager.stop_all_containers()
    logger.info("Terminal platform shut down.")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

app.include_router(auth_routes.router, prefix="/api/auth")
app.include_router(terminal_routes.router, prefix="/api/terminal")
app.include_router(security_routes.router, prefix="/api/admin/security")
app.include_router(users_routes.router, prefix="/api/admin")


@app.get("/api/health")
async def health():
    return {"status": "healthy", "timestamp": now_ts()}


@app.get("/api/ready")
async def ready():
    docker_ok = container_manager.is_available()
    return {
        "status": "ready",
        "docker_available": docker_ok,
        "timestamp": now_ts(),
    }


# ---------------------------------------------------------------------------
# Global error handler
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    logger.error("Unhandled error: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error."},
    )
