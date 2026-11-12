"use client"


import { useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useToastLocal } from "@/components/Toast";
import { securityListSettings, securityUpdateSetting } from "@/lib/api";
import { Settings, Lock, Clock, HardDrive, Monitor, AlertTriangle, User, Terminal } from "lucide-react";

const SETTINGS = [
  { key: "registration_enabled", label: "New user registration", icon: User, type: "select", options: ["enabled", "disabled"], description: "Allow new users to create accounts." },
  { key: "maintenance_mode", label: "Maintenance mode", icon: AlertTriangle, type: "select", options: ["disabled", "enabled"], description: "Disable the platform for all non-admin users." },
  { key: "max_concurrent_users", label: "Maximum concurrent users", icon: Monitor, type: "number", description: "Cap total simultaneous platform users." },
  { key: "max_sessions_per_user", label: "Max terminal sessions per user", icon: Terminal, type: "number", description: "How many concurrent terminals a user may open." },
  { key: "max_session_duration_seconds", label: "Max session duration (seconds)", icon: Clock, type: "number", description: "How long a terminal session may run before expiration." },
  { key: "idle_timeout_seconds", label: "Idle timeout (seconds)", icon: Clock, type: "number", description: "Time after which an idle terminal is disconnected." },
  { key: "max_command_time_seconds", label: "Max command execution time (seconds)", icon: Lock, type: "number", description: "Maximum time a single command may run." },
];

export default function AdminSettings() {
  const { user } = useAuth();
  const { toast } = useToastLocal();
  const [settings, setSettings] = useState<Record<string, string>>({});
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
      const res = await securityListSettings();
      setSettings(res || {});
    } catch (err: any) {
      toast({ title: "Error", description: err?.message || "Failed to load settings.", type: "error" });
    } finally {
      setLoading(false);
    }
  }

  async function save(key: string, value: string) {
    try {
      await securityUpdateSetting(key, value);
      setSettings((prev) => ({ ...prev, [key]: value }));
      toast({ title: "Saved", description: `${key} updated.`, type: "success" });
    } catch (err: any) {
      toast({ title: "Save failed", description: err?.data?.detail || err?.message, type: "error" });
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
            <Settings className="h-5 w-5 text-[#38bdf8]" />
          </div>
          <h1 className="font-semibold text-white tracking-tight">System Settings</h1>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-3xl mx-auto">
          <h2 className="text-xl font-bold text-white mb-6">Platform Configuration</h2>
          <div className="space-y-4">
            {SETTINGS.map((s) => {
              const current = settings[s.key];
              return (
                <div key={s.key} className="panel p-5">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <div className="flex h-6 w-6 items-center justify-center rounded bg-[#18181c] border border-[#27272a] text-[#38bdf8]">
                        <s.icon className="h-3 w-3" />
                      </div>
                      <div>
                        <div className="text-sm font-medium text-white">{s.label}</div>
                        <div className="text-xs text-gray-500">{s.description}</div>
                      </div>
                    </div>
                  </div>
                  {s.type === "select" ? (
                    <select
                      className="input w-48"
                      value={current || s.options?.[0]}
                      onChange={(e) => save(s.key, e.target.value)}
                    >
                      {s.options?.map((o) => (
                        <option key={o} value={o}>{o}</option>
                      ))}
                    </select>
                  ) : (
                    <input
                      className="input w-48"
                      type="number"
                      min="0"
                      value={current || ""}
                      onChange={(e) => save(s.key, e.target.value)}
                      placeholder="0"
                    />
                  )}
                </div>
              );
            })}
          </div>

          <div className="mt-8 panel p-5">
            <h3 className="text-sm font-semibold text-white mb-3">Per-user resource limits</h3>
            <p className="text-xs text-gray-500 mb-4">
              Set CPU, RAM, disk, and process limits for individual users on the
              <a href="/admin/users" className="text-[#38bdf8] hover:underline">User Management</a> page.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
