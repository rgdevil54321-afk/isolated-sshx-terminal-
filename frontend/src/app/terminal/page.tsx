"use client";

import dynamic from "next/dynamic";
import { useRouter } from "next/router";
import { useAuth } from "@/components/AuthProvider";
import { useMounted } from "@/lib/useMounted";

const TerminalEditor = dynamic(() => import("@/components/TerminalEditor"), {
  ssr: false,
});

export default function TerminalPage() {
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

  if (!isAuthenticated) {
    router.push("/login");
    return null;
  }

  return <div className="flex h-full"><TerminalEditor /></div>;
}
