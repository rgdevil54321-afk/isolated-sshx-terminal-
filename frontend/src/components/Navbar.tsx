"use client"

import Link from "next/link";
import { useRouter } from "next/router";
import { useAuth } from "./AuthProvider";
import { LogOut, Monitor, LayoutDashboard, ShieldAlert, Settings, User, Terminal, LogIn } from "lucide-react";

const navItem = (icon: any, label: string, href: string, active: boolean) => {
  const Icon = icon;
  return (
    <Link
      href={href}
      className={`flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
        active
          ? "bg-[#18181c] text-[#38bdf8] border border-[#38bdf8]/40"
          : "text-gray-400 hover:text-white hover:bg-[#18181c]"
      }`}
    >
      <Icon className="w-5 h-5" />
      {label}
    </Link>
  );
};

export function Navbar() {
  const { user, logout, isAuthenticated } = useAuth();
  const router = useRouter();
  const pathname = router.pathname;

  const isAdmin = pathname.startsWith("/admin");

  if (!isAuthenticated) return null;

  return (
    <div className="flex h-full flex-col">
      {/* Top bar */}
      <header className="h-14 border-b border-[#27272a] bg-[#0a0a0c]/80 backdrop-blur flex items-center justify-between px-5 shrink-0 z-10">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded bg-gradient-to-br from-[#38bdf8] to-[#22d3ee] flex items-center justify-center text-[#0a0a0c] font-bold text-xs shadow-[0_0_12px_rgba(56,189,248,0.5)]">
            TT
          </div>
          <span className="font-semibold tracking-tight text-white">TermTerminal</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-400 hidden md:block">
            {user?.username} <span className="text-[#38bdf8] font-mono text-[10px] ml-1">{user?.is_admin ? "ADMIN" : "USER"}</span>
          </span>
          <button
            onClick={logout}
            className="flex items-center gap-2 text-xs font-medium text-gray-300 hover:text-white px-3 py-2 rounded hover:bg-[#18181c] transition"
          >
            <LogOut className="w-4 h-4" /> Sign out
          </button>
        </div>
      </header>

      {/* Sidebar */}
      <nav className="flex-1 overflow-y-auto border-r border-[#27272a] bg-[#0f0f11]/60 px-3 py-4">
        {!isAdmin ? (
          <>
            <div className="px-3 mb-4 text-[10px] font-semibold text-gray-500 uppercase tracking-wider">Terminal</div>
            {navItem(Terminal, "Terminal", "/dashboard", pathname === "/dashboard")}
            <div className="mt-8 px-3 mb-4 text-[10px] font-semibold text-gray-500 uppercase tracking-wider">Account</div>
            {navItem(User, "Profile", "/dashboard/profile", pathname === "/dashboard/profile")}
          </>
        ) : (
          <>
            <div className="px-3 mb-4 text-[10px] font-semibold text-gray-500 uppercase tracking-wider">Admin</div>
            {navItem(LayoutDashboard, "Overview", "/admin", pathname === "/admin")}
            {navItem(Monitor, "Terminals", "/admin/terminals", pathname === "/admin/terminals")}
            {navItem(User, "Users", "/admin/users", pathname === "/admin/users")}
            {navItem(ShieldAlert, "Security", "/admin/security", pathname === "/admin/security")}
            {navItem(Settings, "Settings", "/admin/settings", pathname === "/admin/settings")}
          </>
        )}
      </nav>
    </div>
  );
}
