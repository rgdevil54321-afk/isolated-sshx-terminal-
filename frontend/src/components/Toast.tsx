"use client"

import * as React from "react";
import { useToast, type Toast } from "@/lib/useToast";

const ToastContext = React.createContext<ReturnType<typeof useToast> | null>(null);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const hooks = useToast();
  return <ToastContext.Provider value={hooks}>{children}</ToastContext.Provider>;
}

export function useToastLocal() {
  const ctx = React.useContext(ToastContext);
  if (!ctx) throw new Error("useToastLocal must be used within ToastProvider");
  return ctx;
}

const TYPE_STYLE: Record<"default" | "error" | "success", string> = {
  default: "border-[#27272a] bg-[#111114] text-gray-200",
  error: "border-[#ef4444] bg-[#111114] text-[#fca5a5]",
  success: "border-[#22c55e] bg-[#111114] text-[#86efac]",
};

export function Toast({ toast }: { toast: Toast }) {
  return (
    <div
      key={toast.id}
      className={`flex items-start gap-3 p-4 rounded-lg border animate-in fade-in slide-in-from-right-2 duration-300 ${TYPE_STYLE[toast.type]}`}
    >
      <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#18181c] text-gray-200">
        {toast.type === "error" ? (
          <svg className="h-3 w-3" fill="currentColor" viewBox="0 0 20 20"><path d="M10 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM9.5 15a3 3 0 1 1 6 0v3a3 3 0 1 1-6 0v-3Z" clipRule="evenodd" /></svg>
        ) : toast.type === "success" ? (
          <svg className="h-3 w-3" fill="currentColor" viewBox="0 0 20 20"><path d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm3.707-9.293a1 1 0 0 0-1.414-1.414L9 10.586 7.707 9.293a1 1 0 0 0-1.414 1.414l2 2a1 1 0 0 0 1.414 0l4-4Z" /></svg>
        ) : (
          <svg className="h-3 w-3" fill="currentColor" viewBox="0 0 20 20"><path d="M10 5a3 3 0 1 1 6 0v3a3 3 0 0 1-6 0v-3Zm-4 7a3 3 0 1 0 6 0v3a3 3 0 0 0-6 0v-3Z" /></svg>
        )}
      </div>
      <div className="flex flex-col gap-1">
        <p className="text-sm font-semibold">{toast.title}</p>
        {toast.description && <p className="text-xs text-gray-400">{toast.description}</p>}
      </div>
      <button
        onClick={() => React.useContext(ToastContext)?.dismiss(toast.id)}
        className="ml-auto flex h-6 w-6 shrink-0 items-center justify-center rounded-full p-0 text-gray-400 hover:text-white transition"
      >
        <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M4.293 4.293a1 1 0 0 1 1.414 0L10 8.586l4.293-4.293a1 1 0 1 1 1.414 1.414L11.414 10l4.293 4.293a1 1 0 0 1-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 0 1-1.414-1.414L8.586 10 4.293 5.707a1 1 0 0 1 0-1.414Z" clip-rule="evenodd" /></svg>
      </button>
    </div>
  );
}

export function Toaster({ position = "bottom-center" }: { position?: string }) {
  const { toasts } = useToastLocal();
  return (
    <div
      className={`fixed z-50 gap-4 p-4 ${position === "bottom-center" ? "bottom-0 left-1/2 -translate-x-1/2" : "top-0 right-0"}`}
    >
      {toasts.map((t) => (
        <Toast key={t.id} toast={t} />
      ))}
    </div>
  );
}
