"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/router";
import { useAuth } from "@/components/AuthProvider";
import { terminalListSessions, terminalStats } from "@/lib/api";
import { useMounted } from "@/lib/useMounted";
import { Terminal, Monitor, ShieldAlert, Activity, Lock } from "lucide-react";

export default function Dashboard() {
  const mounted = useMounted();
  if (!mounted) {
    return (
      <div className="flex h-full items-center justify-center bg-[#0a0a0c]">
        <div className="h-8 w-8 rounded-full border-4 border-[#38bdf8]/30 border-t-[#38bdf8] animate-[spin_1s_linear_infinite]" />
      </div>
    );
  }
  const router = useRouter();
  const { user, isAuthenticated } = useAuth();
  const [sessions, setSessions] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated) {
      router.push("/login");
      return;
    }
    load();
  }, [isAuthenticated, router]);

  async function load() {
    setLoading(true);
    try {
      const [s, st] = await Promise.all([
        terminalListSessions().catch(() => []),
        terminalStats("current").catch(() => null),
      ]);
      setSessions(Array.isArray(s) ? s : []);
      setStats(st);
    } catch {
      setSessions([]);
    } finally {
      setLoading(false);
    }
  }

  const running = sessions.filter((s: any) => s.status === "running").length;

  return (
    <div className="flex h-full flex-col bg-[#0a0a0c]">
      <header className="h-14 border-b border-[#27272a] bg-[#0a0a0c]/60 backdrop-blur flex items-center justify-between px-6 shrink-0 z-10">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#18181c] border border-[#27272a]">
            <Terminal className="h-5 w-5 text-[#38bdf8]" />
          </div>
          <h1 className="font-semibold text-white tracking-tight">Terminal</h1>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-400">{user?.username}</span>
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#166534]/20 text-[#4ade80] text-xs border border-[#166534]/40 px-2">
            Online
          </span>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-5xl mx-auto">
          <div className="mb-8">
            <h2 className="text-xl font-bold text-white mb-2">Welcome back, {user?.username}</h2>
            <p className="text-gray-400">
              Your isolated terminal is ready. Each session runs in its own sandboxed
              container with private filesystem and resource limits.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            <div className="panel p-4">
              <div className="text-2xl font-bold text-white">{running}</div>
              <p className="text-xs text-gray-500">Active sessions</p>
            </div>
            <div className="panel p-4">
              <div className="text-2xl font-bold text-white">2</div>
              <p className="text-xs text-gray-500">Max sessions</p>
            </div>
            <div className="panel p-4">
              <div className="text-2xl font-bold text-white">Running</div>
              <p className="text-xs text-gray-500">Status</p>
            </div>
            <div className="panel p-4">
              <div className="text-2xl font-bold text-white">
                {(user?.role || "user").charAt(0).toUpperCase() + (user?.role || "user").slice(1)}
              </div>
              <p className="text-xs text-gray-500">Role</p>
            </div>
          </div>

          <div className="mb-8">
            <h3 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
              <Activity className="h-4 w-4" /> Your terminal sessions
            </h3>
            <div className="panel p-4">
              {loading ? (
                <div className="h-32 flex items-center justify-center text-gray-500">Loading sessions...</div>
              ) : sessions.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-8 text-center text-gray-500">
                  <Terminal className="h-12 w-12 text-gray-700 mb-3" />
                  <p>No active sessions. Open your terminal to start one.</p>
                  <Link href="/terminal" className="mt-4 btn-primary px-4 py-2 text-sm">
                    Open Terminal
                  </Link>
                </div>
              ) : (
                <div className="space-y-3">
                  {sessions.map((s: any) => (
                    <div key={s.id} className="flex items-center justify-between p-3 rounded bg-[#0f0f11] border border-[#27272a]/50">
                      <div className="flex items-center gap-3">
                        <div className="flex h-8 w-8 items-center justify-center rounded bg-[#18181c] text-[#38bdf8]">
                          <Terminal className="h-4 w-4" />
                        </div>
                        <div>
                          <div className="text-sm font-medium text-white">Session {s.id.slice(0, 8)}</div>
                          <div className="text-xs text-gray-500">
                            {s.status} · {new Date((s.created_at || 0) * 1000).toLocaleString()}
                          </div>
                        </div>
                      </div>
                      <Link
                        href="/terminal"
                        className="btn-ghost px-3 py-1.5 text-xs border border-[#27272a] hover:border-[#38bdf8] hover:text-[#38bdf8]"
                      >
                        Open
                      </Link>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
