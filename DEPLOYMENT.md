# Multi-User Isolated Web Terminal Platform — Deployment Guide

Production-ready deployment on a KVM VPS. The platform provides one isolated
container per user, role-based access control (admin / user), IP banning,
configurable resource limits, and a modern web terminal (xterm.js) over
authenticated WebSockets.

## Supported deployment environments

| Environment | Init system | Notes |
|-------------|-------------|-------|
| KVM VPS (Linux) | systemd | Recommended. Full Docker isolation. |
| KVM VPS (Linux) | none / manual | Run with `nohup`/`supervisord`/`docker`. Documented below. |
| Development (any OS) | none | Docker optional; auth/DB/WebSocket flows work, containers degrade gracefully. |

The application does **not** require systemd. A `run.sh` launcher and a
`docker-compose.yml` are provided for environments without systemd.

## Architecture summary

- **Backend:** Python FastAPI (root `backend/`).
- **Frontend:** Next.js 14 + Tailwind + xterm.js (root `frontend/`).
- **Database:** SQLite (single file, `data/terminal_panel.db`), WAL mode,
  trivial backups.
- **Isolation:** one Docker container per user; terminal tabs use `docker exec`
  inside the user's container. Containers run as non-root, read-only rootfs,
  all capabilities dropped, `no-new-privileges`, `network=none`, no Docker
  socket mounted, memory/CPU/pids limits.
- **Auth:** bcrypt password hashing, server-side SQLite sessions issued as an
  `HttpOnly Secure SameSite=Strict` cookie, short-lived JWT WebSocket upgrade
  tokens, double-submit CSRF, trusted-proxy IP resolution.

## 1. Provision the VPS

A standard KVM VPS (e.g. 2 vCPU / 4 GB RAM / 50 GB SSD) running Ubuntu 22.04+
or Debian 12 is sufficient for ~2,000 registered users with configurable
concurrent limits.

```bash
# As root or a sudo user
apt-get update
apt-get install -y python3 python3-pip python3-venv git curl ca-certificates
```

### Docker (required for container isolation on production)

```bash
# Install Docker (official convenience script)
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
usermod -aG docker $USER
newgrp docker
# Verify
docker run hello-world
```

Security: the Docker daemon socket (`/var/run/docker.sock`) is only accessed by
the backend. **Do not** mount the socket into user containers. For additional
isolation, run the backend under a restricted user or use rootless Docker with
user namespaces.

## 2. Clone and install the application

```bash
git clone <your-repo> /opt/terminal-panel
cd /opt/terminal-panel
```

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
# Edit .env (see section 3)
```

### Frontend

```bash
cd ../frontend
npm install
npm run build
```

## 3. Environment configuration

Copy `backend/.env.example` to `backend/.env` and adjust:

| Variable | Purpose | Example |
|----------|---------|---------|
| `HOST` / `PORT` | Bind address | `0.0.0.0`, `8001` |
| `SECRET_KEY` | Signs sessions/JWTs | strong random string |
| `SESSION_TTL_SECONDS` | Session cookie lifetime | `86400` |
| `WS_TOKEN_TTL_SECONDS` | WS upgrade token lifetime | `900` |
| `TRUSTED_PROXIES` | Reverse proxy CIDRs (X-Forwarded-For) | `127.0.0.1,::1,10.0.0.0/8` |
| `DB_PATH` | SQLite file location | `data/terminal_panel.db` |
| `DOCKER_ENABLED` | Set `false` to run without Docker (dev) | `true` |
| `DOCKER_HOST` | Docker daemon socket | `unix:///var/run/docker.sock` |
| `TERMINAL_IMAGE` | Container image | `ubuntu:22.04` |
| `DEFAULT_RAM_LIMIT_MB` / `DEFAULT_CPU_LIMIT` | Per-user limits | `512`, `1.0` |
| `MAX_CONCURRENT_USERS` | Platform concurrency cap | `2000` |
| `LOGIN_RATE_LIMIT` / `REGISTER_RATE_LIMIT` | Rate limiting | `5` / `3` |
| `CORS_ORIGINS` | Allowed dashboard origins | `https://panel.example.com` |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` / `ADMIN_USERNAME` | Bootstrap admin | set strong values |

Generate a strong secret:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

## 4. Database initialization

Run once to create schema and bootstrap settings:

```bash
cd backend
source venv/bin/activate
python -c "from app.database import init_db; init_db()"
```

The admin account is bootstrapped automatically on first start when
`ADMIN_EMAIL` / `ADMIN_PASSWORD` are set. Change the default password
immediately after first login.

## 5. Running the service

### Option A: systemd (recommended)

Create `/etc/systemd/system/terminal-panel.service`:

```ini
[Unit]
Description=Multi-User Isolated Web Terminal Platform
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=terminal-panel
WorkingDirectory=/opt/terminal-panel/backend
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/terminal-panel/backend/venv/bin/python run.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now terminal-panel
systemctl status terminal-panel
```

### Option B: without systemd (run.sh)

```bash
cd /opt/terminal-panel/backend
source venv/bin/activate
nohup python run.py > logs/server.log 2>&1 &
echo $! > run/terminal-panel.pid
```

Stop: `kill $(cat run/terminal-panel.pid)`.

### Option C: Docker Compose

A `docker-compose.yml` at the project root orchestrates backend + frontend
(nginx) with a bind-mounted Docker socket:

```yaml
services:
  backend:
    build: ./backend
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./backend/data:/opt/terminal-panel/backend/data
    environment:
      - DOCKER_HOST=unix:///var/run/docker.sock
    restart: unless-stopped
  frontend:
    build: ./frontend
    restart: unless-stopped
```

## 6. Reverse proxy (nginx) with HTTPS and WebSocket support

Install nginx and obtain a certificate (Certbot / Let's Encrypt).

```nginx
server {
    listen 80;
    server_name panel.example.com;
    location / { return 301 https://$host$request_uri; }
}

server {
    listen 443 ssl http2;
    server_name panel.example.com;

    ssl_certificate /etc/letsencrypt/live/panel.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/panel.example.com/privkey.pem;

    # Trust this proxy for X-Forwarded-For
    set_real_ip_from 127.0.0.1;
    real_ip_header X-Forwarded-For;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 86400s;
    }

    location /api/terminal/ws {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }
}
```

Key security points:
- `TRUSTED_PROXIES` in `.env` must include the nginx IP so `X-Forwarded-For`
  is honored; never trust forwarding headers from untrusted sources.
- WebSocket upgrade requires the `Connection: upgrade` / `Upgrade: websocket`
  headers to pass through.
- Cookies are `Secure` — they require HTTPS to be sent by browsers.

## 7. Service management (without systemd)

If systemd is unavailable, use `supervisord` or a simple init script:

```ini
; /etc/supervisor/conf.d/terminal-panel.conf
[program:terminal-panel]
directory=/opt/terminal-panel/backend
command=/opt/terminal-panel/backend/venv/bin/python run.py
autostart=true
autorestart=true
user=terminal-panel
```

## 8. Backup and recovery

The entire state is in `backend/data/terminal_panel.db` (SQLite) plus uploaded
config in `.env`. Back up the database file:

```bash
# Daily cron example
0 3 * * * cp /opt/terminal-panel/backend/data/terminal_panel.db /backups/terminal-panel-$(date +%F).db
```

Recovery: stop the service, replace `data/terminal_panel.db` with the backup,
restart.

## 9. Updates

```bash
cd /opt/terminal-panel
git pull
cd backend && source venv/bin/activate && pip install -r requirements.txt && python -c "from app.database import init_db; init_db()"
cd ../frontend && npm install && npm run build
systemctl restart terminal-panel
```

Database migrations are additive (`CREATE TABLE IF NOT EXISTS`); existing data
is preserved.

## 10. Security checklist

- [ ] `SECRET_KEY` changed from default.
- [ ] `ADMIN_PASSWORD` changed from default.
- [ ] `TRUSTED_PROXIES` set to your reverse proxy only.
- [ ] Docker socket **not** mounted into user containers.
- [ ] HTTPS enabled; cookies are `Secure`.
- [ ] `registration_enabled` toggled off when not accepting signups.
- [ ] Firewall: only 22 (SSH), 80, 443 exposed.
- [ ] Run backend as a non-root user.
- [ ] Review `security_events` table and IP bans regularly via the admin dashboard.

## 11. Admin vs user access

- Admin dashboard: `https://panel.example.com/admin` (requires admin role).
- User dashboard: `https://panel.example.com/dashboard`.
- Terminal: `https://panel.example.com/terminal`.

All enforcement is backend-side. Frontend-only hiding is supplemented by
permission checks on every API/WebSocket endpoint. Restricted users receive:
`You are not allowed to perform this action.`
