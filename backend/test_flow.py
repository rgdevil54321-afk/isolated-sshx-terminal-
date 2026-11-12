"""
Functional test flow for the terminal platform backend.

Run:  python test_flow.py   (server must be running on http://127.0.0.1:8001)
"""

import json
import os
import urllib.request
import urllib.error
import http.cookiejar

BASE = "http://127.0.0.1:8001"

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

csrf_token = None


def get_cookie(name):
    for c in cj:
        if c.name == name:
            return c.value
    return None


def req(method, path, body=None, use_csrf=False):
    global csrf_token
    url = BASE + path
    data = None
    h = {"Content-Type": "application/json"}
    if use_csrf:
        # Ensure we have a CSRF token (from /csrf or from a prior login/set-cookie).
        if csrf_token is None:
            s, b2 = req("GET", "/api/auth/csrf")
            csrf_token = get_cookie("csrf_token") or (b2.get("csrf_token") if isinstance(b2, dict) else None)
        h["x-csrf-token"] = csrf_token
    if body is not None:
        data = json.dumps(body).encode()
    # Send all stored cookies on every request (simulates HTTPS where secure
    # cookies are returned by the browser). Must be set before Request creation.
    cookies = [f"{c.name}={c.value}" for c in cj]
    if cookies:
        h["Cookie"] = "; ".join(cookies)
    r = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        resp = opener.open(r)
        content = resp.read()
        status = resp.status
    except urllib.error.HTTPError as e:
        content = e.read()
        status = e.code
    # Refresh csrf cookie after login/register responses set it.
    ct = get_cookie("csrf_token")
    if ct:
        csrf_token = ct
    try:
        return status, json.loads(content) if content else None
    except Exception:
        return status, content.decode(errors="replace")


def show(label, status, body):
    print(f"[{label}] HTTP {status} :: {json.dumps(body) if not isinstance(body, str) else body[:200]}")


passed = 0
failed = 0


def check(label, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS: {label}")
    else:
        failed += 1
        print(f"  FAIL: {label} {detail}")


# 1. Health
s, b = req("GET", "/api/health")
show("health", s, b)
check("health ok", s == 200)

# 2. Register a normal user
s, b = req("POST", "/api/auth/register", {
    "username": "alice", "email": "alice@example.com", "password": "Secret1234!"
}, use_csrf=True)
show("register alice", s, b)
check("register alice 201", s == 201, str(b))

# 3. Register again -> conflict
s, b = req("POST", "/api/auth/register", {
    "username": "alice", "email": "alice2@example.com", "password": "Secret1234!"
}, use_csrf=True)
check("dup username 409", s == 409, str(b))

# 4. Login with wrong password -> 401
s, b = req("POST", "/api/auth/login", {"username": "alice", "password": "Wrong!"}, use_csrf=True)
show("login wrong pw", s, b)
check("wrong pw 401", s == 401, str(b))

# 5. Login correct
s, b = req("POST", "/api/auth/login", {"username": "alice", "password": "Secret1234!"}, use_csrf=True)
show("login alice", s, b)
check("login alice 200", s == 200, str(b))
check("has ws_token", bool(b and b.get("ws_token")), str(b))
check("alice not admin", b.get("user", {}).get("is_admin") is False, str(b))

# 6. Get me
s, b = req("GET", "/api/auth/me")
show("me alice", s, b)
check("me returns user", s == 200 and b.get("role") == "user", str(b))

# 7. Normal user cannot access admin overview
s, b = req("GET", "/api/admin/overview")
show("alice admin overview", s, b)
check("normal user blocked from admin 403", s == 403, str(b))

# 8. Login as admin (bootstrapped)
s, b = req("POST", "/api/auth/login", {
    "username": "admin", "password": os.environ.get("ADMIN_PASSWORD", "change-me-immediately")
}, use_csrf=True)
show("login admin", s, b)
check("admin login 200", s == 200, str(b))
check("admin is admin", b.get("user", {}).get("is_admin") is True, str(b))

# 9. Admin overview
s, b = req("GET", "/api/admin/overview")
show("admin overview", s, b)
check("admin overview 200", s == 200, str(b))
check("has total_users", isinstance(b.get("total_users"), int), str(b))

# 10. Ban IP needs CSRF (without -> 403)
s, b = req("POST", "/api/admin/security/ip-bans", {
    "ip": "10.99.99.99", "reason": "test ban", "ban_type": "temporary",
})
show("ban ip no csrf", s, b)
check("ban needs csrf 403", s == 403, str(b))

# 11. Ban IP with CSRF (temporary, far future)
s, b = req("POST", "/api/admin/security/ip-bans", {
    "ip": "10.99.99.99", "reason": "test ban", "ban_type": "temporary",
    "expires_at": int(__import__("time").time()) + 86400
}, use_csrf=True)
show("ban ip", s, b)
check("ban ip 201", s == 201, str(b))

# 12. List IP bans
s, b = req("GET", "/api/admin/security/ip-bans")
show("list bans", s, b)
check("list bans 200", s == 200, str(b))

# 13. Security events list
s, b = req("GET", "/api/admin/security/events")
show("security events", s, b)
check("security events 200", s == 200, str(b))

# 14. Settings
s, b = req("GET", "/api/admin/security/settings")
show("settings", s, b)
check("settings 200", s == 200, str(b))

# 15. Update a setting
s, b = req("POST", "/api/admin/security/settings", {"key": "maintenance_mode", "value": "disabled"}, use_csrf=True)
show("update setting", s, b)
check("update setting 200", s == 200, str(b))

# 16. Logout
s, b = req("POST", "/api/auth/logout")
show("logout", s, b)
check("logout 200", s == 200, str(b))

# 17. me after logout -> 401
s, b = req("GET", "/api/auth/me")
check("me after logout 401", s == 401, str(b))

print(f"\n{passed} passed, {failed} failed")
if failed:
    raise SystemExit(1)
