"""
Security layer.

- Trusted-proxy client IP resolution: X-Forwarded-For / X-Real-IP are only
  honored when the immediate connection comes from a trusted proxy.
- In-memory rate limiters (login, registration, WebSocket) keyed by client IP.
- IP ban enforcement.
- Audit/security event logging.
"""

from __future__ import annotations

import ipaddress
import os
import threading
import time
from collections import defaultdict
from typing import Optional

from fastapi import Request

from .database import run_db
from .logging import get_logger
from .models import (
    add_ip_ban,
    is_ip_banned,
    log_login_attempt,
    log_security_event,
)

logger = get_logger(__name__)


def _parse_cidrs(value: Optional[str]) -> list[ipaddress._BaseNetwork]:
    if not value:
        return []
    nets = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            nets.append(ipaddress.ip_network(part, strict=False))
        except ValueError:
            logger.warning("Invalid trusted proxy CIDR ignored: %s", part)
    return nets


TRUSTED_PROXIES = _parse_cidrs(os.getenv("TRUSTED_PROXIES", "127.0.0.1,::1"))


def get_client_ip(request: Request) -> str:
    """Resolve the real client IP.

    Only honor forwarding headers when the immediate peer is a trusted proxy.
    Never blindly trust user-supplied headers.
    """
    peer = request.client.host if request.client else None
    peer_is_trusted = peer is not None and any(
        ipaddress.ip_address(peer) in net for net in TRUSTED_PROXIES
    )

    if peer_is_trusted:
        # X-Forwarded-For: <client>, <proxy1>, <proxy2> ... take the leftmost.
        xff = request.headers.get("x-forwarded-for")
        if xff:
            first = xff.split(",")[0].strip()
            if first:
                return first
        xri = request.headers.get("x-real-ip")
        if xri:
            return xri.strip()
    # Fall back to the direct peer (untrusted or no proxy).
    return peer or "0.0.0.0"


# ---------------------------------------------------------------------------
# Rate limiting (in-memory, single instance; Redis recommended for scale-out)
# ---------------------------------------------------------------------------

class _RateLimiter:
    """Fixed-window rate limiter keyed by identifier."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._records: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            window_start = now - self.window_seconds
            rec = self._records[key]
            rec[:] = [t for t in rec if t > window_start]
            if len(rec) >= self.max_requests:
                return False
            rec.append(now)
            return True

    def remaining(self, key: str) -> int:
        now = time.time()
        with self._lock:
            window_start = now - self.window_seconds
            rec = self._records[key]
            rec[:] = [t for t in rec if t > window_start]
            return max(0, self.max_requests - len(rec))


login_limiter = _RateLimiter(
    int(os.getenv("LOGIN_RATE_LIMIT", "5")),
    int(os.getenv("LOGIN_RATE_WINDOW_SECONDS", "60")),
)
register_limiter = _RateLimiter(
    int(os.getenv("REGISTER_RATE_LIMIT", "3")),
    int(os.getenv("REGISTER_RATE_WINDOW_SECONDS", "60")),
)
ws_limiter = _RateLimiter(
    int(os.getenv("WS_RATE_LIMIT", "10")),
    int(os.getenv("WS_RATE_WINDOW_SECONDS", "60")),
)


def check_login_rate(ip: str) -> bool:
    return login_limiter.is_allowed(ip)


def check_register_rate(ip: str) -> bool:
    return register_limiter.is_allowed(ip)


def check_ws_rate(ip: str) -> bool:
    return ws_limiter.is_allowed(ip)


# ---------------------------------------------------------------------------
# IP ban enforcement
# ---------------------------------------------------------------------------


async def enforce_ip_ban(ip: str) -> Optional[dict]:
    """Return the active ban dict if the IP is banned, else None."""
    return await run_db(is_ip_banned, ip)


def record_login_attempt(ip: Optional[str], username: str, success: bool) -> None:
    try:
        run_db(log_login_attempt, ip, username, success)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to record login attempt: %s", exc)


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------


async def audit(
    event_type: str,
    *,
    severity: str = "info",
    ip: Optional[str] = None,
    user_id: Optional[int] = None,
    details: Optional[str] = None,
) -> None:
    try:
        await run_db(
            log_security_event,
            event_type,
            severity,
            ip,
            user_id,
            details,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to write audit event: %s", exc)
