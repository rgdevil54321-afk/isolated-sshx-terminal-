"use client";

import Link from "next/link";
import { useRouter } from "next/router";
import { useEffect } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useMounted } from "@/lib/useMounted";
import { Terminal, ShieldCheck, Zap, Monitor, Layers } from "lucide-react";

export default function Landing() {
  const mounted = useMounted();
  if (!mounted) {
    return (
      <div className="flex h-full items-center justify-center bg-[#0a0a0c]">
        <div className="h-8 w-8 rounded-full border-4 border-[#38bdf8]/30 border-t-[#38bdf8] animate-[spin_1s_linear_infinite]" />
      </div>
    );
  }
  const router = useRouter();
  const { isAuthenticated, loading } = useAuth();

  useEffect(() => {
    if (isAuthenticated) {
      router.push("/dashboard");
    }
  }, [isAuthenticated, router]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center bg-[#0a0a0c]">
        <div className="flex h-8 w-8 items-center justify-center rounded-full border-4 border-[#38bdf8]/30 border-t-[#38bdf8] animate-[spin_1s_linear_infinite]" />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col items-center justify-center bg-[#0a0a0c] p-6">
      <div className="flex flex-1 flex-col items-center justify-center gap-8 text-center max-w-2xl px-4">
        <div className="flex h-16 w-16 items-center justify-center rounded-xl bg-gradient-to-br from-[#38bdf8] to-[#22d3ee] shadow-[0_0_20px_rgba(56,189,248,0.4)]">
          <Terminal className="h-8 w-8 text-[#0a0a0c]" />
        </div>
        <div className="flex flex-col gap-2">
          <h1 className="text-4xl md:text-6xl font-bold text-white tracking-tight">TermTerminal</h1>
          <p className="text-gray-400 text-lg max-w-xl">
            Secure, isolated terminal access for every user. Built for community
            VPS drops, giveaways, and public server access.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 w-full max-w-md">
          {featureBox(Zap, "Isolated", "Every user gets a dedicated sandboxed terminal.")}
          {featureBox(ShieldCheck, "Private", "Users cannot see or touch other sessions.")}
          {featureBox(Monitor, "Admin controlled", "Full admin oversight and resource limits.")}
        </div>

        <div className="flex flex-col gap-3 w-full max-w-md">
          <Link href="/login" className="btn-primary w-full py-3 text-center">
            Sign in
          </Link>
          <Link href="/register" className="btn-ghost w-full py-3 text-center border border-[#27272a]">
            Create account
          </Link>
        </div>
      </div>
    </div>
  );
}

function featureBox(icon: any, title: string, desc: string) {
  const Icon = icon;
  return (
    <div className="flex flex-col gap-2 p-4 rounded-lg bg-[#0f0f11] border border-[#27272a]">
      <div className="flex h-8 w-8 items-center justify-center rounded bg-[#18181c] border border-[#27272a]">
        <Icon className="h-4 w-4 text-[#38bdf8]" />
      </div>
      <h3 className="text-sm font-semibold text-white">{title}</h3>
      <p className="text-xs text-gray-500 leading-relaxed">{desc}</p>
    </div>
  );
}
