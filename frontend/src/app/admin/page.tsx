"use client"


import { useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useToastLocal } from "@/components/Toast";
import { adminOverview, securityListBans } from "@/lib/api";
import {
  LayoutDashboard,
  Monitor,
  Users,
  ShieldAlert,
  HardDrive,
  Activity,
  Terminal,
  AlertCircle,
} from "lucide-react";

export default function AdminOverview() {
  const { user } = useAuth();
  const { toast } = useToastLocal();
  const [data, setData] = useState<any>(null);
  const [bans, setBans] = useState<any[]>([]);
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
      const [d, b] = await Promise.all([adminOverview(), securityListBans(true, 5, 0)]);
      setData(d);
      setBans(Array.isArray(b?.bans) ? b.bans : []);
    } catch (err: any) {
      toast({ title: "Error", description: err?.message || "Failed to load dashboard.", type: "error" });
    } finally {
      setLoading(false);
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
            <LayoutDashboard className="h-5 w-5" />
          </div>
          <h1 className="font-semibold text-white tracking-tight">Admin Dashboard</h1>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-400">{user?.username} (admin)</span>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-6xl mx-auto">
          <div className="mb-6">
            <h2 className="text-xl font-bold text-white">Platform Overview</h2>
            <p className="text-gray-400">System-wide statistics and resource summary.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
            {[
              { label: "Total users", value: data?.total_users ?? "--", icon: Users, color: "#38bdf8" },
              { label: "Active sessions", value: data?.active_sessions ?? "--", icon: Terminal, color: "#22d3ee" },
              { label: "Max concurrent", value: data?.max_concurrent_users ?? "--", icon: Activity, color: "#818cf8" },
              { label: "Banned IPs", value: bans.length, icon: ShieldAlert, color: "#ef4444" },
              { label: "Registration", value: data?.registration_enabled ? "On" : "Off", icon: AlertCircle, color: "#a78bfa" },
              { label: "Maintenance", value: data?.maintenance_mode ? "On" : "Off", icon: AlertCircle, color: "#f59e0b" },
            ].map((item) => (
              <div key={item.label} className="panel p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex h-6 w-6 items-center justify-center rounded bg-[#18181c] text-[{item.color}]">
                    <item.icon className="h-3 w-3" />
                  </div>
                </div>
                <div className="text-2xl font-bold text-white">{item.value}</div>
                <p className="text-xs text-gray-500">{item.label}</p>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Banned IPs */}
            <div className="panel p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-white">IP Blacklist</h3>
                <a href="/admin/security" className="text-xs text-[#38bdf8] hover:underline">Manage</a>
              </div>
              <div className="space-y-2">
                {bans.length === 0 ? (
                  <p className="text-xs text-gray-500">No active IP bans.</p>
                ) : (
                  bans.map((b: any) => (
                    <div key={b.id} className="flex items-center justify-between p-2 rounded bg-[#18181c] border border-[#27272a]/40 text-sm">
                      <div>
                        <div className="text-gray-200 font-mono">{b.ip}</div>
                        <div className="text-[10px] text-gray-500">{b.reason}</div>
                      </div>
                      <span className={`badge border ${
                        b.ban_type === "permanent" ? "bg-[#ef4444]/20 text-[#f87171] border-[#ef4444]/40" : "bg-[#f59e0b]/20 text-[#fbbf24] border-[#f59e0b]/40"
                      }`}>
                        {b.ban_type}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Quick actions */}
            <div className="panel p-5">
              <h3 className="text-sm font-semibold text-white mb-4">Quick actions</h3>
              <div className="grid grid-cols-1 gap-3">
                <a href="/admin/users" className="btn-ghost w-full py-2 text-left border border-[#27272a] hover:border-[#38bdf8] hover:text-[#38bdf8]">
                  Manage users
                </a>
                <a href="/admin/security" className="btn-ghost w-full py-2 text-left border border-[#27272a] hover:border-[#38bdf8] hover:text-[#38bdf8]">
                  Security & bans
                </a>
                <a href="/admin/terminals" className="btn-ghost w-full py-2 text-left border border-[#27272a] hover:border-[#38bdf8] hover:text-[#38bdf8]">
                  Active terminals
                </a>
                <a href="/admin/settings" className="btn-ghost w-full py-2 text-left border border-[#27272a] hover:border-[#38bdf8] hover:text-[#38bdf8]">
                  System settings
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
