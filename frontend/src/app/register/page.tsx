"use client"


import { useState } from "react";
import { useRouter } from "next/router";
import { useToastLocal } from "@/components/Toast";
import { register } from "@/lib/api";
import { useMounted } from "@/lib/useMounted";
import { UserPlus, Mail, Lock } from "lucide-react";

export default function RegisterPage() {
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
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await register(username, email, password);
      toast({ title: "Account created", description: "Please sign in.", type: "success" });
      router.push("/login");
    } catch (err: any) {
      const msg = err?.data?.detail || err?.message || "Registration failed.";
      toast({ title: "Registration failed", description: msg, type: "error" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-full items-center justify-center bg-[#0a0a0c] p-6">
      <div className="w-full max-w-md">
        <div className="flex flex-col gap-2 mb-8">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-[#38bdf8] to-[#22d3ee] text-[#0a0a0c]">
            <UserPlus className="h-5 w-5" />
          </div>
          <h2 className="text-2xl font-bold text-white">Create account</h2>
          <p className="text-gray-400">Join the community terminal platform.</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1">Username</label>
            <input
              className="input"
              placeholder="alice"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1">Email</label>
            <input
              type="email"
              className="input"
              placeholder="alice@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
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
              autoComplete="new-password"
              required
            />
            <div className="flex items-center gap-1 pt-1">
              <Lock className="h-4 w-4 text-gray-600" />
            </div>
          </div>
          <button className="btn-primary w-full py-3" disabled={loading}>
            {loading ? "Creating account..." : "Create account"}
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-gray-500">
          Already have an account?{" "}
          <a href="/login" className="text-[#38bdf8] hover:underline">Sign in</a>
        </p>
      </div>
    </div>
  );
}
