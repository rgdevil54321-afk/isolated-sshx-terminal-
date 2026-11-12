"use client"


import { useEffect, useState, useCallback } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useToastLocal } from "@/components/Toast";
import {
  adminListUsers,
  adminSuspendUser,
  adminUnsuspendUser,
  adminBanUser,
  adminUnbanUser,
  adminTerminateSession,
  adminSetResourceLimits,
  adminGetUser,
  adminUserHistory,
} from "@/lib/api";
import { User, ShieldAlert, Lock, Terminal, Search, MoreHorizontal, AlertTriangle, Edit } from "lucide-react";

export default function AdminUsers() {
  const { user } = useAuth();
  const { toast } = useToastLocal();
  const [users, setUsers] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [role, setRole] = useState("");
  const [isActive, setIsActive] = useState("");
  const [isBanned, setIsBanned] = useState("");
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<any>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    if (user?.role !== "admin") {
      toast({ title: "Access denied", description: "You are not allowed to perform this action.", type: "error" });
      return;
    }
    load();
  }, [user, toast]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminListUsers({ search: search || undefined, role: role || undefined, is_active: isActive ? 1 : undefined, is_banned: isBanned ? 1 : undefined });
      setUsers(Array.isArray(res?.users) ? res.users : []);
      setTotal(res?.total ?? users.length);
    } catch (err: any) {
      toast({ title: "Error", description: err?.message || "Failed to load users.", type: "error" });
    } finally {
      setLoading(false);
    }
  }, [search, role, isActive, isBanned, toast, users.length]);

  async function openDetail(id: number) {
    setDetailLoading(true);
    try {
      const res = await adminGetUser(id);
      setDetail(res?.user || res);
    } catch (err: any) {
      toast({ title: "Error", description: err?.message || "Failed to load user details.", type: "error" });
    } finally {
      setDetailLoading(false);
    }
  }

  async function runAction(fn: () => Promise<any>, label: string) {
    try {
      await fn();
      toast({ title: label, description: "Action completed.", type: "success" });
      load();
      if (detail) openDetail(detail.user_id);
    } catch (err: any) {
      toast({ title: label + " failed", description: err?.data?.detail || err?.message, type: "error" });
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
            <User className="h-5 w-5 text-[#38bdf8]" />
          </div>
          <h1 className="font-semibold text-white tracking-tight">User Management</h1>
        </div>
        <div className="flex items-center gap-2">
          <input
            className="input w-64"
            placeholder="Search users..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-7xl mx-auto">
          {detail && (
            <div className="mb-6 panel p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-sm font-semibold text-white">User: {detail.username}</h3>
                  <p className="text-xs text-gray-500">{detail.email} • ID {detail.id} • Role: {detail.role}</p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => runAction(() => (detail.is_active ? adminUnsuspendUser(detail.id) : adminSuspendUser(detail.id)), detail.is_active ? "Unsuspend" : "Suspend")}
                    className="btn-ghost px-3 py-2 text-xs border border-[#27272a] hover:border-[#38bdf8]"
                  >
                    {detail.is_active ? "Suspend" : "Unsuspend"}
                  </button>
                  <button
                    onClick={() => runAction(() => (detail.is_banned ? adminUnbanUser(detail.id) : adminBanUser(detail.id)), detail.is_banned ? "Unban" : "Ban")}
                    className="btn-ghost px-3 py-2 text-xs border border-[#27272a] hover:border-[#ef4444] hover:text-[#ef4444]"
                  >
                    {detail.is_banned ? "Unban" : "Ban"}
                  </button>
                  <button onClick={() => setDetail(null)} className="btn-ghost px-3 py-2 text-xs border border-[#27272a]">Close</button>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-3 rounded bg-[#18181c] border border-[#27272a]/50">
                  <div className="text-[10px] text-gray-500 uppercase">Status</div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`w-2 h-2 rounded-full ${detail.is_active ? "bg-[#22c55e]" : "bg-[#ef4444]"}`} />
                    <span className="text-sm">{detail.is_active ? "Active" : detail.is_banned ? "Banned" : "Suspended"}</span>
                  </div>
                </div>
                <div className="p-3 rounded bg-[#18181c] border border-[#27272a]/50">
                  <div className="text-[10px] text-gray-500 uppercase">Sessions</div>
                  <div className="text-sm font-mono text-white mt-1">
                    {(detail.sessions || []).length} total
                  </div>
                </div>
              </div>
              <div className="mt-5">
                <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Recent command history</h4>
                <div className="h-32 overflow-y-auto p-3 rounded bg-[#0a0a0c] border border-[#27272a] font-mono text-xs text-gray-400 space-y-1">
                  {detail.history?.map((h: any) => (
                    <div key={h.id} className="truncate">{h.command}</div>
                  )) || <p className="text-gray-600">No history.</p>}
                </div>
              </div>
            </div>
          )}

          <div className="panel p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-white">Users ({total})</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="text-left border-b border-[#27272a] text-gray-500 text-[11px] uppercase">
                    <th className="pb-3">User</th>
                    <th className="pb-3">Role</th>
                    <th className="pb-3">Status</th>
                    <th className="pb-3">Sessions</th>
                    <th className="pb-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u: any) => (
                    <tr key={u.id} className="border-b border-[#27272a]/40 hover:bg-[#18181c]/40 transition group">
                      <td className="pb-3">
                        <div className="flex items-center gap-2">
                          <div className="flex h-6 w-6 items-center justify-center rounded bg-[#18181c] text-[#38bdf8] text-[10px]">
                            {u.username.charAt(0).toUpperCase()}
                          </div>
                          <div>
                            <div className="text-gray-200 font-medium">{u.username}</div>
                            <div className="text-[10px] text-gray-500">{u.email}</div>
                          </div>
                        </div>
                      </td>
                      <td className="pb-3">
                        <span className={`badge border px-2 py-0.5 ${u.role === "admin" ? "bg-[#a78bfa]/20 text-[#c4b5fd] border-[#a78bfa]/40" : "bg-[#818cf8]/20 text-[#a5b4fc] border-[#818cf8]/40"}`}>
                          {u.role}
                        </span>
                      </td>
                      <td className="pb-3">
                        <span className={`flex items-center gap-1 ${u.is_active && !u.is_banned ? "text-[#22c55e]" : u.is_banned ? "text-[#ef4444]" : "text-[#f59e0b]"}`}>
                          <span className="w-1.5 h-1.5 rounded-full" />
                          {u.is_active ? "Active" : u.is_banned ? "Banned" : "Suspended"}
                        </span>
                      </td>
                      <td className="pb-3 text-gray-300">—</td>
                      <td className="pb-3 text-right">
                        <button
                          onClick={() => openDetail(u.id)}
                          className="btn-ghost px-2.5 py-1.5 text-[10px] border border-[#27272a] hover:border-[#38bdf8] hover:text-[#38bdf8] rounded"
                        >
                          <MoreHorizontal className="w-3 h-3" /> Manage
                        </button>
                      </td>
                    </tr>
                  ))}
                  {users.length === 0 && (
                    <tr>
                      <td colSpan={5} className="pb-8 text-center text-gray-500 text-sm">No users found.</td>
                    </tr>
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
