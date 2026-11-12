"""
Database layer for the Multi-User Isolated Web Terminal Platform.

Uses SQLite (single file, trivial backups, zero extra daemon) with WAL mode
for concurrent read/write access. All blocking sqlite calls are designed to be
executed in a thread pool from async FastAPI endpoints (see `run_db`).
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time as _time
from contextlib import contextmanager
from typing import Any, Callable, Optional

from .logging import get_logger

logger = get_logger(__name__)

DB_PATH = os.getenv("DB_PATH", "data/terminal_panel.db")

# A module-level lock serializes writes so we never hit "database is locked"
# under concurrent access from the thread pool.
_write_lock = threading.RLock()

# Thread-local connections are not used; each operation opens/closes its own
# connection. This is simplest and correct for a single-process deployment.


def get_conn() -> sqlite3.Connection:
    """Open a new SQLite connection with sane defaults."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


@contextmanager
def transaction():
    """Context manager providing a connection inside a write lock transaction."""
    with _write_lock:
        conn = get_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def init_db() -> None:
    """Create all tables and run idempotent migrations."""
    with transaction() as conn:
        conn.executescript(_SCHEMA)
    logger.info("Database initialized at %s", DB_PATH)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
-- Users ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    is_active INTEGER NOT NULL DEFAULT 1,
    is_banned INTEGER NOT NULL DEFAULT 0,
    ban_reason TEXT,
    created_at INTEGER NOT NULL,
    last_login INTEGER,
    -- Per-user resource limit overrides (NULL => use system default)
    ram_limit_mb INTEGER,
    cpu_limit REAL,
    disk_limit_mb INTEGER,
    pids_limit INTEGER,
    max_sessions INTEGER,
    max_session_duration_seconds INTEGER,
    idle_timeout_seconds INTEGER,
    max_command_time_seconds INTEGER
);

-- Sessions (server-side auth sessions) --------------------------------
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ip TEXT,
    user_agent TEXT,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    last_activity INTEGER NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);

-- Terminal sessions (a user's isolated terminal environments) ---------
CREATE TABLE IF NOT EXISTS terminal_sessions (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    container_name TEXT,
    exec_id TEXT,
    status TEXT NOT NULL DEFAULT 'starting' CHECK (status IN ('starting','running','stopped','expired')),
    created_at INTEGER NOT NULL,
    last_activity INTEGER NOT NULL,
    expires_at INTEGER,
    cols INTEGER DEFAULT 80,
    rows INTEGER DEFAULT 24,
    command TEXT DEFAULT '/bin/bash'
);
CREATE INDEX IF NOT EXISTS idx_terminal_sessions_user_id ON terminal_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_terminal_sessions_status ON terminal_sessions(status);

-- IP bans -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ip_bans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip TEXT NOT NULL,
    reason TEXT NOT NULL,
    ban_type TEXT NOT NULL DEFAULT 'permanent' CHECK (ban_type IN ('permanent','temporary')),
    banned_by INTEGER REFERENCES users(id),
    banned_at INTEGER NOT NULL,
    expires_at INTEGER,
    is_active INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_ip_bans_ip ON ip_bans(ip);
CREATE INDEX IF NOT EXISTS idx_ip_bans_active ON ip_bans(is_active);

-- Security / audit events ---------------------------------------------
CREATE TABLE IF NOT EXISTS security_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'info',
    ip TEXT,
    user_id INTEGER REFERENCES users(id),
    details TEXT,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_security_events_type ON security_events(event_type);
CREATE INDEX IF NOT EXISTS idx_security_events_created_at ON security_events(created_at);

-- Login attempts ------------------------------------------------------
CREATE TABLE IF NOT EXISTS login_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip TEXT,
    username TEXT,
    success INTEGER NOT NULL DEFAULT 0,
    attempted_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_login_attempts_ip ON login_attempts(ip);

-- System settings -----------------------------------------------------
CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at INTEGER NOT NULL,
    updated_by INTEGER REFERENCES users(id)
);

-- Command history (per user, optional, only when permitted) -----------
CREATE TABLE IF NOT EXISTS command_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    terminal_session_id TEXT,
    command TEXT NOT NULL,
    executed_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_command_history_user_id ON command_history(user_id);
"""


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def now_ts() -> int:
    return int(_time.time())


def run_db(func: Callable[..., Any], *args, **kwargs) -> Any:
    """Run a blocking sqlite call in a thread pool.

    FastAPI/Starlette provides `run_in_threadpool`; here we delegate to
    asyncio.to_thread when an event loop is running so callers can use this
    from both sync and async contexts.
    """
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop: execute directly (sync context / tests).
        return func(*args, **kwargs)
    return asyncio.get_event_loop().run_in_executor(None, lambda: func(*args, **kwargs))


def fetch_one(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
    cur = conn.execute(sql, params)
    return cur.fetchone()


def fetch_all(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    cur = conn.execute(sql, params)
    return cur.fetchall()


def execute(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> sqlite3.Cursor:
    return conn.execute(sql, params)


def last_insert_id(conn: sqlite3.Connection) -> int:
    cur = conn.execute("SELECT last_insert_rowid()")
    return cur.fetchone()[0]
