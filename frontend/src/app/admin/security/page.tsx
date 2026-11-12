"use client"


import { useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useToastLocal } from "@/components/Toast";
import {
  securityListBans,
  securityAddBan,
  securityRemoveBan,
  securityCheckBan,
  securityListEvents,
} from "@/lib/api";
import { ShieldAlert, Terminal, Ban, History, Clock, Search } from "lucide-react";

export default function AdminSecurity() {
  const { user } = useAuth();
  const { toast } = useToastLocal();
  const [bans, setBans] = useState<any[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  interface BanForm {
  ip: string;
  reason: string;
  ban_type: "permanent" | "temporary";
  expires_at: string;
}
const [banForm, setBanForm] = useState<BanForm>({ ip: "", reason: "", ban_type: "permanent", expires_at: "" });
  const [checkIp, setCheckIp] = useState("");
  const [checkResult, setCheckResult] = useState<any>(null);

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
      const [b, e] = await Promise.all([securityListBans(true, 50, 0), securityListEvents(undefined, undefined, 50, 0)]);
      setBans(Array.isArray(b?.bans) ? b.bans : []);
      setEvents(Array.isArray(e?.events) ? e.events : []);
    } catch (err: any) {
      toast({ title: "Error", description: err?.message || "Failed to load security data.", type: "error" });
    } finally {
      setLoading(false);
    }
  }

  async function addBan() {
    try {
      await securityAddBan(banForm.ip, banForm.reason, banForm.ban_type, banForm.expires_at ? Date.parse(banForm.expires_at) / 1000 : undefined);
      toast({ title: "Ban added", type: "success" });
      setBanForm({ ip: "", reason: "", ban_type: "permanent", expires_at: "" });
      load();
    } catch (err: any) {
      toast({ title: "Ban failed", description: err?.data?.detail || err?.message, type: "error" });
    }
  }

  async function removeBan(ip: string) {
    if (!window.confirm(`Remove ban for IP ${ip}?`)) return;
    try {
      await securityRemoveBan(ip);
      toast({ title: "Ban removed", type: "success" });
      load();
    } catch (err: any) {
      toast({ title: "Remove failed", description: err?.message, type: "error" });
    }
  }

  async function checkBan() {
    try {
      const res = await securityCheckBan(checkIp);
      setCheckResult(res);
    } catch (err: any) {
      toast({ title: "Check failed", description: err?.message, type: "error" });
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
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-[#ef4444] to-[#f97316] text-[#0a0a0c]">
            <ShieldAlert className="h-5 w-5" />
          </div>
          <h1 className="font-semibold text-white tracking-tight">Security Management</h1>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-6xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
            {/* Ban IP */}
            <div className="panel p-5">
              <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
                <Ban className="h-4 w-4" /> Ban IP Address
              </h3>
              <form onSubmit={(e) => { e.preventDefault(); addBan(); }} className="space-y-3">
                <div className="space-y-2">
                  <label className="text-xs font-medium text-gray-400">IP address</label>
                  <input
                    className="input"
                    placeholder="1.2.3.4"
                    value={banForm.ip}
                    onChange={(e) => setBanForm({ ...banForm, ip: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-medium text-gray-400">Reason</label>
                  <input
                    className="input"
                    placeholder="e.g. brute force login attempts"
                    value={banForm.reason}
                    onChange={(e) => setBanForm({ ...banForm, reason: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-medium text-gray-400">Type</label>
                  <select
                    className="input"
                    value={banForm.ban_type}
                    onChange={(e) => setBanForm({ ...banForm, ban_type: e.target.value as any })}
                  >
                    <option value="permanent">Permanent</option>
                    <option value="temporary">Temporary</option>
                  </select>
                </div>
                {banForm.ban_type === "temporary" && (
                  <div className="space-y-2">
                    <label className="text-xs font-medium text-gray-400">Expires at</label>
                    <input
                      type="datetime-local"
                      className="input"
                      value={banForm.expires_at}
                      onChange={(e) => setBanForm({ ...banForm, expires_at: e.target.value })}
                    />
                  </div>
                )}
                <button className="btn-danger w-full py-2">Add Ban</button>
              </form>
            </div>

            {/* IP check */}
            <div className="panel p-5">
              <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
                <Search className="h-4 w-4" /> Check IP Ban Status
              </h3>
              <div className="space-y-3">
                <div className="space-y-2">
                  <label className="text-xs font-medium text-gray-400">IP address</label>
                  <input
                    className="input"
                    placeholder="1.2.3.4"
                    value={checkIp}
                    onChange={(e) => setCheckIp(e.target.value)}
                  />
                </div>
                <button onClick={checkBan} className="btn-ghost w-full py-2 border border-[#27272a] hover:border-[#38bdf8]">
                  Check
                </button>
                {checkResult && (
                  <div className={`p-3 rounded border ${checkResult.banned ? "border-[#ef4444]/40 bg-[#ef4444]/10" : "border-[#22c55e]/40 bg-[#22c55e]/10"}`}>
                    <div className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${checkResult.banned ? "bg-[#ef4444]" : "bg-[#22c55e]"}`} />
                      <span className="text-sm font-medium">{checkResult.banned ? "BANNED" : "Not banned"}</span>
                    </div>
                    {checkResult.ban && (
                      <div className="mt-2 text-xs text-gray-400">
                        {checkResult.ban.reason} ({checkResult.ban.ban_type})
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Stats */}
            <div className="panel p-5">
              <h3 className="text-sm font-semibold text-white mb-4">Overview</h3>
              <div className="space-y-3">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-400">Active bans</span>
                  <span className="text-white font-mono">{bans.length}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-400">Recent events</span>
                  <span className="text-white font-mono">{events.length}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Active bans list */}
          <div className="panel p-5 mb-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <Terminal className="h-4 w-4" /> Active IP Bans
              </h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="text-left border-b border-[#27272a] text-gray-500 text-[11px] uppercase">
                    <th className="pb-3">IP</th>
                    <th className="pb-3">Type</th>
                    <th className="pb-3">Reason</th>
                    <th className="pb-3">Banned at</th>
                    <th className="pb-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {bans.map((b: any) => (
                    <tr key={b.id} className="border-b border-[#27272a]/40">
                      <td className="pb-3 text-gray-200 font-mono">{b.ip}</td>
                      <td className="pb-3">
                        <span className={`badge border px-2 py-0.5 ${b.ban_type === "permanent" ? "bg-[#ef4444]/20 text-[#f87171] border-[#ef4444]/40" : "bg-[#f59e0b]/20 text-[#fbbf24] border-[#f59e0b]/40"}`}>
                          {b.ban_type}
                        </span>
                      </td>
                      <td className="pb-3 text-gray-300 truncate max-w-[200px]">{b.reason}</td>
                      <td className="pb-3 text-xs text-gray-500">{new Date((b.banned_at || 0) * 1000).toLocaleString()}</td>
                      <td className="pb-3 text-right">
                        <button
                          onClick={() => removeBan(b.ip)}
                          className="btn-ghost px-2.5 py-1.5 text-[10px] text-[#ef4444] border border-transparent hover:bg-[#ef4444]/20 rounded"
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                  {bans.length === 0 && (
                    <tr><td colSpan={5} className="pb-8 text-center text-gray-500 text-sm">No active bans.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Security events */}
          <div className="panel p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <History className="h-4 w-4" /> Security Events
              </h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="text-left border-b border-[#27272a] text-gray-500 text-[11px] uppercase">
                    <th className="pb-3">Time</th>
                    <th className="pb-3">Event</th>
                    <th className="pb-3">Severity</th>
                    <th className="pb-3">IP</th>
                    <th className="pb-3">Details</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((e: any) => (
                    <tr key={e.id} className="border-b border-[#27272a]/40">
                      <td className="pb-3 text-xs text-gray-500 font-mono">{new Date((e.created_at || 0) * 1000).toLocaleString()}</td>
                      <td className="pb-3 text-gray-300 truncate max-w-[200px]">{e.event_type}</td>
                      <td className="pb-3">
                        <span className={`badge border px-2 py-0.5 ${e.severity === "warning" ? "bg-[#ef4444]/20 text-[#f87171]" : e.severity === "info" ? "bg-[#38bdf8]/20 text-[#4fd1f8]" : "bg-[#818cf8]/20 text-[#a5b4fc]"}`}>
                          {e.severity}
                        </span>
                      </td>
                      <td className="pb-3 text-xs text-gray-500 font-mono">{e.ip || "—"}</td>
                      <td className="pb-3 text-xs text-gray-400 truncate max-w-[260px]">{e.details || "—"}</td>
                    </tr>
                  ))}
                  {events.length === 0 && (
                    <tr><td colSpan={5} className="pb-8 text-center text-gray-500 text-sm">No events.</td></tr>
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
