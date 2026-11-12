# Multi-User Isolated Web Terminal Platform — Architecture Decisions

## Stack

- **Backend:** Python FastAPI + raw `sqlite3` (SQLite, WAL mode). Single file
  database; trivial backups; zero extra daemon.
- **Frontend:** Next.js 14 (App Router), Tailwind CSS, xterm.js with fit,
  search, and web-links addons.
- **Container runtime:** Docker (one container per user; `docker exec` per
  terminal session).

## Isolation model (defense in depth)

1. **One container per user** (not one per terminal tab). Container startup
   latency (~1–3 s) is paid once per user; additional terminal tabs use
   `docker exec` inside the same user container.
2. Container security:
   - runs as non-root (`uid 1000`)
   - `cap-drop ALL`, `security-opt no-new-privileges:true`
   - `read_only=True` rootfs; only `/tmp` and `/home/appuser/work` are writable
     tmpfs (noexec, nosuid)
   - `network_mode=none` (no network from the container)
   - `memory`, `cpu_quota`, `pids_limit` enforced per container
   - **Docker socket is never mounted** into user containers
   - no privileged host namespaces
3. The backend talks to the Docker daemon over the host socket
   (`unix:///var/run/docker.sock`). That socket must be protected on the host
   (restricted group or rootless Docker).
4. Processes run inside the container only — never on the app's root shell.

## Authentication & sessions

- Passwords hashed with **bcrypt** (never plaintext).
- Server-side sessions stored in SQLite; session cookie is `HttpOnly`,
  `Secure`, `SameSite=Strict`.
- Short-lived JWT (`purpose=ws-upgrade`, ~15 min TTL) used as a WebSocket
  upgrade-token fallback for clients that cannot rely on cookies.
- WebSocket authentication: session cookie preferred, JWT fallback. Expired or
  unauthorized sessions are disconnected.
- All permission checks are backend-side (`require_admin`, ownership
  verification on every terminal/session API). Frontend button hiding is
  supplementary only.

## CSRF

Double-submit pattern: `csrf_token` cookie (non-HttpOnly) echoed as the
`X-CSRF-Token` header on state-changing requests. Safe methods (GET/HEAD/OPTIONS)
are exempt.

## IP resolution (trusted proxy)

Client IP is resolved via `X-Forwarded-For` / `X-Real-IP` **only** when the
immediate peer is in `TRUSTED_PROXIES`. Otherwise the direct peer address is
used. Forwarding headers are never blindly trusted.

## Rate limiting & IP bans

- In-memory fixed-window limiters for login, registration, and WebSocket
  connections (keyed by IP). Redis recommended for multi-instance scale-out.
- IP bans (permanent or temporary) stored in SQLite; blocked from terminal
  access, registration, and VPS-drop participation.
- No automatic permanent ban on a single event — bans require administrator
  action or configurable thresholds.

## Resource limits

Configurable per-user (overriding system defaults): RAM, CPU, disk, pids, max
sessions, max session duration, idle timeout, max command time, max concurrent
users. Enforced per container via Docker limits; concurrency enforced in the
backend.

## Audit logging

Security events (logins, bans, admin actions, setting changes) are written to
the `security_events` table with type, severity, IP, user, and timestamp.

## WebSocket terminal proxy

`/api/terminal/ws` — authenticated WebSocket proxied to a `docker exec` PTY
inside the user's container. Bidirectional byte pumping, PTY resize via
`exec_resize`, reconnection handling, session expiry, and cleanup on disconnect.

## Graceful degradation

When Docker is unavailable (`DOCKER_ENABLED=false` or daemon unreachable), all
container operations raise `DockerUnavailable` and return clear errors. Auth,
DB, WebSocket auth, IP bans, and admin APIs remain fully functional — useful
for development and for degraded operation.

## Data model (SQLite)

- `users` — accounts, roles, per-user resource overrides, ban state.
- `sessions` — server-side auth sessions (indexed by user, expiry).
- `terminal_sessions` — per-user terminal environments (owner-verified).
- `ip_bans` — permanent/temporary bans (indexed by IP, active flag).
- `security_events` — audit log (indexed by type, timestamp).
- `login_attempts` — failed/successful login records.
- `system_settings` — key/value configuration.
- `command_history` — per-user command history (when permitted).

Indexes on foreign keys and frequently filtered columns.

## Threat model

- Users cannot reach other users' containers, the host filesystem, the Docker
  socket, or privileged namespaces.
- Users cannot create admin accounts or privileged terminal links.
- Frontend permission checks are never trusted.
- Resource limits prevent one user from exhausting the host.
