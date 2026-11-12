"use strict";

import { useCallback, useState, useMemo } from "react";

export type ToastType = "default" | "error" | "success";

export interface Toast {
  id: string;
  title: string;
  description?: string;
  type: ToastType;
}

const TOAST_LIMIT = 5;
const TOAST_REMOVE_DELAY = 4000;

export function useToast() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const toast = useCallback(
    (opts: { title: string; description?: string; type?: ToastType }) => {
      const id = Math.random().toString(36).slice(2, 9);
      const newToast: Toast = { id, type: "default", ...opts };
      setToasts((prev) => [newToast, ...prev].slice(0, TOAST_LIMIT));
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, TOAST_REMOVE_DELAY);
      return id;
    },
    []
  );

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return useMemo(
    () => ({ toast, dismiss, toasts }),
    [toast, dismiss, toasts]
  );
}
