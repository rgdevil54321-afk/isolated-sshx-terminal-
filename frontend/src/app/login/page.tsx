"use client"


import { useState } from "react";
import { useRouter } from "next/router";
import { useToastLocal } from "@/components/Toast";
import { login } from "@/lib/api";
import { LogIn, Mail, Lock } from "lucide-react";
import { useMounted } from "@/lib/useMounted";

export default function LoginPage() {
  const mounted = useMounted();
  if (!mounted) {
    return (
      <div className="flex h-full items-center justify-center bg-[#0a0a0c]">
        <div className="h-8 w-8 rounded-full border-4 border-[#38bdf8]/30 border-t-[#38bdf8] animate-[spin_1s_linear_infinite]" />
      </div>
    );
  }
  const router = useRouter();
  const { toast } = useToastLocal();
  const [loading, setLoading] = useState(false);
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await login(identifier, password);
      if (res.ws_token) {
        sessionStorage.setItem("tt_ws_token", res.ws_token);
      }
      router.push("/dashboard");
    } catch (err: any) {
      const msg = err?.data?.detail || err?.message || "Login failed.";
      toast({ title: "Login failed", description: msg, type: "error" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-full items-center justify-center bg-[#0a0a0c] p-6">
      <div className="w-full max-w-md">
        <div className="flex flex-col gap-2 mb-8">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-[#38bdf8] to-[#22d3ee] text-[#0a0a0c]">
            <LogIn className="h-5 w-5" />
          </div>
          <h2 className="text-2xl font-bold text-white">Sign in</h2>
          <p className="text-gray-400">Access your isolated terminal.</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1">Username or email</label>
            <input
              className="input"
              placeholder="alice or alice@example.com"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              autoComplete="username"
              required
            />
            <div className="flex items-center gap-1 pt-1">
              <Mail className="h-4 w-4 text-gray-600" />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1">Password</label>
            <input
              type="password"
              className="input"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
            <div className="flex items-center gap-1 pt-1">
              <Lock className="h-4 w-4 text-gray-600" />
            </div>
          </div>
          <button
            className="btn-primary w-full py-3"
            disabled={loading}
          >
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-gray-500">
          Don't have an account?{" "}
          <a href="/register" className="text-[#38bdf8] hover:underline">Create one</a>
        </p>
      </div>
    </div>
  );
}
