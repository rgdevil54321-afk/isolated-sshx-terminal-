#!/bin/bash
set -e

cd /root/isolated-sshx-terminal-

echo "================================================"
echo "  Multi-User Isolated Terminal Installer"
echo "================================================"

# 1. Detect public IP
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')
echo "[1/6] Detected IP: $PUBLIC_IP"

# 2. Backend deps
echo "[2/6] Installing Python backend deps..."
cd /root/isolated-sshx-terminal-/backend
if [ ! -d venv ]; then
  python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip >/dev/null 2>&1
pip install -r requirements.txt >/dev/null 2>&1

# 3. Backend .env
cat > .env <<'ENV'
HOST=0.0.0.0
PORT=8000
DEBUG=false
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
SESSION_TTL_SECONDS=86400
WS_TOKEN_TTL_SECONDS=900
TRUSTED_PROXIES=127.0.0.1,::1
DB_PATH=data/terminal_panel.db
DOCKER_HOST=unix:///var/run/docker.sock
TERMINAL_IMAGE=ubuntu:22.04
DOCKER_ENABLED=false
DEFAULT_RAM_LIMIT_MB=512
DEFAULT_CPU_LIMIT=1.0
DEFAULT_MAX_SESSIONS=2
MAX_CONCURRENT_USERS=2000
LOGIN_RATE_LIMIT=5
LOGIN_RATE_WINDOW_SECONDS=60
REGISTER_RATE_LIMIT=3
REGISTER_RATE_WINDOW_SECONDS=60
WS_RATE_LIMIT=10
WS_RATE_WINDOW_SECONDS=60
CORS_ORIGINS=http://localhost:3000,http://$PUBLIC_IP:8080
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=ChangeMeImmediately123!
ADMIN_USERNAME=admin
ENV

# 4. Init DB
python -c "from app.database import init_db; init_db()"
echo "[3/6] Backend DB initialized."

# 5. Start backend
if [ -f server.pid ] && kill -0 "$(cat server.pid)" 2>/dev/null; then
  kill "$(cat server.pid)" 2>/dev/null || true
  sleep 1
fi
nohup python run.py > server.log 2>&1 &
echo $! > server.pid
sleep 3
echo "[4/6] Backend started on port 8000 (PID $(cat server.pid))."

# 6. Frontend
cd /root/isolated-sshx-terminal-/frontend
echo "[5/6] Installing frontend deps..."
npm install --quiet --no-audit --no-fund >/dev/null 2>&1 || true
echo "[6/6] Building frontend..."
rm -rf .next
NODE_OPTIONS="--max-old-space-size=1024" npm run build >/dev/null 2>&1

if [ -f frontend.pid ] && kill -0 "$(cat frontend.pid)" 2>/dev/null; then
  kill "$(cat frontend.pid)" 2>/dev/null || true
  sleep 1
fi
PORT=8080 nohup npm start > frontend.log 2>&1 &
echo $! > frontend.pid
sleep 5

echo ""
echo "================================================"
echo "  ALL DONE - ACCESS LINK:"
echo "================================================"
echo "  http://$PUBLIC_IP:8080"
echo ""
echo "  Admin: admin@example.com / ChangeMeImmediately123!"
echo "  User:  register your own at /register"
echo ""
echo "  Backend:  http://$PUBLIC_IP:8000"
echo "  Frontend: http://$PUBLIC_IP:8080"
echo "================================================"
echo ""
echo "NOTE: No 'root' shell access - users get isolated containers."
echo "Change ADMIN_PASSWORD in backend/.env before public use."
echo "Install Docker + set DOCKER_ENABLED=true for real isolation."
