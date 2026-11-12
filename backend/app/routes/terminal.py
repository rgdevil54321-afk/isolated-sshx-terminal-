"""
Terminal session management and WebSocket terminal proxy.

Every terminal session is bound to an authenticated user ID. A user can only
create/connect to their own terminal sessions. The backend proxies a
WebSocket to a `docker exec` PTY inside the user's isolated container.

Security:
  - WebSocket requires authentication (session cookie or short-lived JWT).
  - Ownership is verified before any exec stream is attached.
  - Expired/unauthorized sessions are disconnected.
  - One container per user; exec sessions run as non-root inside it.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Optional

from fastapi import APIRouter, Cookie, Query, WebSocket, WebSocketDisconnect, status
from fastapi import Depends, HTTPException

from ..auth import authenticate_websocket, get_current_user
from ..container import DockerUnavailable, container_manager
from ..database import now_ts, run_db
from ..logging import get_logger
from ..models import (
    add_command_history,
    create_terminal_session,
    get_active_terminal_sessions,
    get_setting,
    get_terminal_session,
    get_terminal_sessions_by_user,
    update_terminal_session,
)
from ..security import audit, check_ws_rate, enforce_ip_ban, get_client_ip

router = APIRouter()
logger = get_logger(__name__)

WS_IDLE_TIMEOUT = int(os.getenv("DEFAULT_IDLE_TIMEOUT_SECONDS", "1800"))


# ---------------------------------------------------------------------------
# HTTP: list the current user's terminal sessions
# ---------------------------------------------------------------------------

@router.get("/sessions")
async def list_terminal_sessions(current_user=Depends(get_current_user)):
    user_id = current_user["user_id"]
    sessions = await run_db(get_terminal_sessions_by_user, user_id)
    return [
        {
            "id": s["id"],
            "status": s["status"],
            "created_at": s["created_at"],
            "last_activity": s["last_activity"],
            "expires_at": s["expires_at"],
            "container_name": s["container_name"],
        }
        for s in sessions
    ]


# ---------------------------------------------------------------------------
# HTTP: get stats for the current user's container
# ---------------------------------------------------------------------------

@router.get("/sessions/{session_id}/stats")
async def session_stats(session_id: str, current_user=Depends(get_current_user)):
    row = await run_db(get_terminal_session, session_id)
    if not row or row["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=404, detail="Not found")
    stats = container_manager.container_stats(current_user["user_id"])
    if stats is None:
        raise HTTPException(status_code=503, detail="Container stats unavailable")
    return stats


# ---------------------------------------------------------------------------
# WebSocket terminal endpoint
# ---------------------------------------------------------------------------

@router.websocket("/ws")
async def terminal_ws(
    websocket: WebSocket,
    token: Optional[str] = Query(default=None),
    session_id: Optional[str] = Cookie(default=None, alias="session_id"),
):
    await websocket.accept()

    ip = get_client_ip(websocket)

    # IP ban check.
    ban = await enforce_ip_ban(ip)
    if ban:
        await websocket.send_json({"type": "error", "message": "You are not allowed to perform this action."})
        await websocket.close(code=4403)
        return

    # WebSocket rate limit.
    if not check_ws_rate(ip):
        await websocket.send_json({"type": "error", "message": "Too many connections. Try again later."})
        await websocket.close(code=4429)
        return

    # Authenticate.
    try:
        user = await authenticate_websocket(websocket, token=token, session_id=session_id)
    except Exception:
        await websocket.send_json({"type": "error", "message": "Not authenticated."})
        await websocket.close(code=4401)
        return

    user_id = user["user_id"]

    # Concurrent user limit.
    active = await run_db(get_active_terminal_sessions)
    try:
        max_users = int(get_setting("max_concurrent_users") or "2000")
    except Exception:
        max_users = 2000
    active_users = {s["user_id"] for s in active}
    if user_id not in active_users and len(active_users) >= max_users:
        await websocket.send_json({"type": "error", "message": "Maximum concurrent users reached."})
        await websocket.close(code=4403)
        return

    # Per-user max sessions.
    try:
        max_sessions = int(get_setting("max_sessions_per_user") or "2")
    except Exception:
        max_sessions = 2
    user_sessions = await run_db(get_terminal_sessions_by_user, user_id)
    running_user_sessions = [s for s in user_sessions if s["status"] == "running"]
    if len(running_user_sessions) >= max_sessions:
        await websocket.send_json({"type": "error", "message": "Maximum sessions reached for your account."})
        await websocket.close(code=4403)
        return

    # Reuse an existing running terminal session, else create one.
    term_session = None
    for s in running_user_sessions:
        term_session = s
        break

    exec_id = None
    container_name = None
    if term_session:
        exec_id = term_session["exec_id"]
        container_name = term_session["container_name"]
    else:
        try:
            exec_info = container_manager.create_exec(user_id)
        except DockerUnavailable:
            await websocket.send_json({"type": "error", "message": "Terminal isolation unavailable."})
            await websocket.close(code=4503)
            return
        except Exception as exc:
            logger.error("Failed to create container for user %d: %s", user_id, exc)
            await websocket.send_json({"type": "error", "message": "Failed to start terminal."})
            await websocket.close(code=4500)
            return
        exec_id = exec_info["exec_id"]
        container_name = exec_info["container_name"]

        expires_at = None
        try:
            duration = int(get_setting("max_session_duration_seconds") or "28800")
            expires_at = int(time.time()) + duration
        except Exception:
            pass

        created = await run_db(
            create_terminal_session,
            session_id=exec_id,
            user_id=user_id,
            container_name=container_name,
            exec_id=exec_id,
            expires_at=expires_at,
        )

    term_id = exec_id

    # Attach to the exec stream.
    try:
        client = container_manager._get_client()
        container = client.containers.get(container_name)
        stream = container.exec_start(exec_id, tty=True, socket=True)
    except DockerUnavailable:
        await websocket.send_json({"type": "error", "message": "Terminal isolation unavailable."})
        await websocket.close(code=4503)
        return
    except Exception as exc:
        logger.error("Failed to attach exec for user %d: %s", user_id, exc)
        await websocket.send_json({"type": "error", "message": "Failed to attach terminal."})
        await websocket.close(code=4500)
        return

    await websocket.send_json(
        {
            "type": "ready",
            "session_id": term_id,
            "user_id": user_id,
            "cols": 80,
            "rows": 24,
        }
    )

    loop = asyncio.get_event_loop()

    async def docker_to_ws():
        try:
            while True:
                data = await loop.run_in_executor(None, stream.recv, 4096)
                if not data:
                    break
                await websocket.send_bytes(data)
        except Exception:
            pass

    async def ws_to_docker():
        try:
            while True:
                msg = await websocket.receive()
                if msg.get("type") == "websocket.disconnect":
                    break
                data = None
                if msg.get("bytes") is not None:
                    data = msg["bytes"]
                elif msg.get("text") is not None:
                    raw = msg["text"]
                    # Control messages are JSON text; everything else is raw input.
                    try:
                        ctrl = json.loads(raw)
                        if isinstance(ctrl, dict):
                            if ctrl.get("type") == "resize":
                                container_manager.resize_exec(
                                    exec_id, int(ctrl.get("cols", 80)), int(ctrl.get("rows", 24))
                                )
                                await run_db(
                                    update_terminal_session,
                                    term_id,
                                    cols=int(ctrl.get("cols", 80)),
                                    rows=int(ctrl.get("rows", 24)),
                                    last_activity=int(time.time()),
                                )
                                continue
                            if ctrl.get("type") == "command":
                                await run_db(
                                    add_command_history,
                                    user_id,
                                    ctrl.get("text", ""),
                                    term_id,
                                )
                                await run_db(
                                    update_terminal_session,
                                    term_id,
                                    last_activity=int(time.time()),
                                )
                                stream.send(ctrl.get("text", "").encode("utf-8"))
                                continue
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        pass
                    data = raw.encode("utf-8")
                if data:
                    await loop.run_in_executor(None, stream.send, data)
                    await run_db(
                        update_terminal_session,
                        term_id,
                        last_activity=int(time.time()),
                    )
        except WebSocketDisconnect:
            pass
        except Exception:
            pass

    try:
        await asyncio.gather(docker_to_ws(), ws_to_docker())
    except Exception:
        pass
    finally:
        await run_db(
            update_terminal_session, term_id, status="stopped", last_activity=int(time.time())
        )
        try:
            stream.close()
        except Exception:
            pass
        try:
            await websocket.close(code=status.WS_1001_NORMAL_CLOSURE)
        except Exception:
            pass
