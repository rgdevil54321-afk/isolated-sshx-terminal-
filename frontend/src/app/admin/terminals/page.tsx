"use client"


import { useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useToastLocal } from "@/components/Toast";
import { adminListActiveTerminals, adminTerminateSession } from "@/lib/api";
import { Terminal, Monitor, User, AlertTriangle } from "lucide-react";

export default function AdminTerminals() {
  const { user } = useAuth();
  const { toast } = useToastLocal();
  const [terminals, setTerminals] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (user?.role !== "admin") {
      toast({ title: "Access denied", description: "You are not allowed to perform this action.", type: "error" });
      return;
    }
    load();
  }, [user, toast]);

  async function load() {
    setLoading(true);
    try {
      const res = await adminListActiveTerminals();
      setTerminals(Array.isArray(res?.terminals) ? res.terminals : []);
    } catch (err: any) {
      toast({ title: "Error", description: err?.message || "Failed to load terminals.", type: "error" });
    } finally {
      setLoading(false);
    }
  }

  async function terminate(termId: string, userId: number) {
    if (!window.confirm("Terminate this terminal session?")) return;
    try {
      await adminTerminateSession(userId, termId);
      toast({ title: "Terminated", type: "success" });
      load();
    } catch (err: any) {
      toast({ title: "Terminate failed", description: err?.message, type: "error" });
    }
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center bg-[#0a0a0c]">
        <div className="h-8 w-8 rounded-full border-4 border-[#38bdf8]/30 border-t-[#38bdf8] animate-[spin_1s_linear_infinite]" />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-[#0a0a0c]">
      <header className="h-14 border-b border-[#27272a] bg-[#0a0a0c]/60 backdrop-blur flex items-center justify-between px-6 shrink-0 z-10">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#18181c] border border-[#27272a]">
            <Monitor className="h-5 w-5 text-[#38bdf8]" />
          </div>
          <h1 className="font-semibold text-white tracking-tight">Active Terminals</h1>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto">
          <div className="mb-6">
            <h2 className="text-xl font-bold text-white">All Active Terminal Sessions</h2>
            <p className="text-gray-400">Administrators can view and terminate any active terminal.</p>
          </div>

          <div className="panel p-5">
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="text-left border-b border-[#27272a] text-gray-500 text-[11px] uppercase">
                    <th className="pb-3">Session ID</th>
                    <th className="pb-3">Owner</th>
                    <th className="pb-3">Container</th>
                    <th className="pb-3">Started</th>
                    <th className="pb-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {terminals.map((t: any) => (
                    <tr key={t.id} className="border-b border-[#27272a]/40">
                      <td className="pb-3 text-gray-200 font-mono text-xs truncate max-w-[180px]">{t.id}</td>
                      <td className="pb-3">
                        <div className="flex items-center gap-2">
                          <div className="flex h-6 w-6 items-center justify-center rounded bg-[#18181c] text-[#38bdf8] text-[10px]">
                            {t.username.charAt(0).toUpperCase()}
                          </div>
                          <div className="text-sm text-gray-200">{t.username}</div>
                          <div className="text-[10px] text-gray-500">UID {t.user_id}</div>
                        </div>
                      </td>
                      <td className="pb-3 text-xs text-gray-400 font-mono truncate max-w-[160px]">{t.container_name}</td>
                      <td className="pb-3 text-xs text-gray-500">{new Date((t.created_at || 0) * 1000).toLocaleString()}</td>
                      <td className="pb-3 text-right">
                        <button
                          onClick={() => terminate(t.id, t.user_id)}
                          className="btn-ghost px-2.5 py-1.5 text-[10px] text-[#ef4444] border border-transparent hover:bg-[#ef4444]/20 rounded"
                        >
                          <AlertTriangle className="w-3 h-3 mr-1" /> Terminate
                        </button>
                      </td>
                    </tr>
                  ))}
                  {terminals.length === 0 && (
                    <tr><td colSpan={5} className="pb-8 text-center text-gray-500 text-sm">No active terminals.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
