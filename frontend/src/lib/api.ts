// API client for the terminal platform frontend.
//
// Uses fetch with credentials (cookies) and implements the double-submit CSRF
// pattern: the csrf_token cookie is read and echoed as the X-CSRF-Token header
// on state-changing requests.

import { getCookie, setCookie, deleteCookie } from "./cookies";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8001";

export interface User {
  user_id: number;
  username: string;
  email: string;
  role: string;
  is_admin: boolean;
}

let csrfTokenValue: string | null = null;

export function setCsrfToken(token: string | null) {
  csrfTokenValue = token;
}

export function getCsrfToken(): string | null {
  if (csrfTokenValue) return csrfTokenValue;
  return getCookie("csrf_token") || null;
}

async function ensureCsrf() {
  if (!getCsrfToken()) {
    try {
      const res = await fetch(`${API_BASE}/api/auth/csrf`, { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        csrfTokenValue = data.csrf_token || null;
      }
    } catch {
      // ignore
    }
  }
}

export async function apiRequest(
  path: string,
  { method = "GET", body, headers = {}, useCsrf = false }: { method?: string; body?: any; headers?: Record<string, string>; useCsrf?: boolean } = {}
): Promise<Response> {
  const h: Record<string, string> = { ...headers };
  if (body && !(body instanceof FormData)) {
    h["Content-Type"] = "application/json";
  }
  if (useCsrf) {
    await ensureCsrf();
    const tok = getCsrfToken();
    if (tok) {
      h["X-CSRF-Token"] = tok;
      // Browsers send the cookie automatically; we also make sure it's set.
    }
  }
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: h,
    credentials: "include",
    body: body ? (body instanceof FormData ? body : JSON.stringify(body)) : undefined,
  });
  return res;
}

export async function apiJson<T = any>(
  path: string,
  opts: { method?: string; body?: any; headers?: Record<string, string>; useCsrf?: boolean } = {}
): Promise<T> {
  const res = await apiRequest(path, opts);
  let data: any = null;
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    data = await res.json();
  } else {
    data = await res.text();
  }
  if (!res.ok) {
    const err: any = new Error(data?.detail || data || `Request failed (${res.status})`);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data as T;
}

export async function me(): Promise<User> {
  return apiJson<User>("/api/auth/me");
}

export async function login(username: string, password: string): Promise<{ user: User; ws_token: string }> {
  ensureCsrf();
  return apiJson<{ user: User; ws_token: string }>("/api/auth/login", {
    method: "POST",
    body: { username, password },
    useCsrf: true,
  });
}

export async function register(username: string, email: string, password: string): Promise<{ message: string }> {
  ensureCsrf();
  return apiJson<{ message: string }>("/api/auth/register", {
    method: "POST",
    body: { username, email, password },
    useCsrf: true,
  });
}

export async function logout(): Promise<{ message: string }> {
  return apiJson<{ message: string }>("/api/auth/logout", { method: "POST", useCsrf: true });
}

export async function csrfToken(): Promise<string> {
  const res = await fetch(`${API_BASE}/api/auth/csrf`, { credentials: "include" });
  const data = await res.json();
  csrfTokenValue = data.csrf_token;
  return data.csrf_token;
}

// Admin APIs
export async function adminOverview(): Promise<any> {
  return apiJson("/api/admin/overview");
}
export async function adminListUsers(params?: { search?: string; role?: string; is_active?: number; is_banned?: number; limit?: number; offset?: number }): Promise<any> {
  const qs = new URLSearchParams(params as any).toString();
  return apiJson(`/api/admin/users?${qs}`);
}
export async function adminGetUser(userId: number): Promise<any> {
  return apiJson(`/api/admin/users/${userId}`);
}
export async function adminSuspendUser(userId: number): Promise<any> {
  return apiJson(`/api/admin/users/${userId}/suspend`, { method: "POST", useCsrf: true });
}
export async function adminUnsuspendUser(userId: number): Promise<any> {
  return apiJson(`/api/admin/users/${userId}/unsuspend`, { method: "POST", useCsrf: true });
}
export async function adminBanUser(userId: number, reason?: string): Promise<any> {
  return apiJson(`/api/admin/users/${userId}/ban`, { method: "POST", body: { reason }, useCsrf: true });
}
export async function adminUnbanUser(userId: number): Promise<any> {
  return apiJson(`/api/admin/users/${userId}/unban`, { method: "POST", useCsrf: true });
}
export async function adminTerminateSession(userId: number, sessionId: string): Promise<any> {
  return apiJson(`/api/admin/users/${userId}/sessions/${sessionId}/terminate`, { method: "POST", useCsrf: true });
}
export async function adminSetResourceLimits(userId: number, limits: any): Promise<any> {
  return apiJson(`/api/admin/users/${userId}/resource-limits`, { method: "PUT", body: limits, useCsrf: true });
}
export async function adminUserHistory(userId: number, limit = 100, offset = 0): Promise<any> {
  return apiJson(`/api/admin/users/${userId}/history?limit=${limit}&offset=${offset}`);
}

export async function adminListActiveTerminals(): Promise<any> {
  return apiJson("/api/admin/terminals");
}

// Security APIs
export async function securityListBans(activeOnly = true, limit = 100, offset = 0): Promise<any> {
  return apiJson(`/api/admin/security/ip-bans?active_only=${activeOnly}&limit=${limit}&offset=${offset}`);
}
export async function securityAddBan(ip: string, reason: string, banType: string, expiresAt?: number): Promise<any> {
  return apiJson("/api/admin/security/ip-bans", { method: "POST", body: { ip, reason, ban_type: banType, expires_at: expiresAt }, useCsrf: true });
}
export async function securityRemoveBan(ip: string): Promise<any> {
  return apiJson(`/api/admin/security/ip-bans/${encodeURIComponent(ip)}`, { method: "DELETE", useCsrf: true });
}
export async function securityCheckBan(ip: string): Promise<any> {
  return apiJson(`/api/admin/security/ip-bans/check/${encodeURIComponent(ip)}`);
}
export async function securityListEvents(eventType?: string, severity?: string, limit = 100, offset = 0): Promise<any> {
  const qs = new URLSearchParams({ event_type: eventType || "", severity: severity || "", limit: String(limit), offset: String(offset) }).toString();
  return apiJson(`/api/admin/security/events?${qs}`);
}
export async function securityListSettings(): Promise<any> {
  return apiJson("/api/admin/settings");
}
export async function securityUpdateSetting(key: string, value: string): Promise<any> {
  return apiJson("/api/admin/security/settings", { method: "POST", body: { key, value }, useCsrf: true });
}

// Terminal APIs
export async function terminalListSessions(): Promise<any> {
  return apiJson("/api/terminal/sessions");
}
export async function terminalStats(sessionId: string): Promise<any> {
  return apiJson(`/api/terminal/sessions/${sessionId}/stats`);
}

export function wsUrl(token?: string): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = window.location.host;
  const qs = token ? `?token=${encodeURIComponent(token)}` : "";
  return `${protocol}//${host}/api/terminal/ws${qs}`;
}
