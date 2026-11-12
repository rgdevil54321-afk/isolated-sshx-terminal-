"use client"

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { me, logout } from "@/lib/api";
import type { User } from "@/lib/api";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  isAuthenticated: boolean;
  refetch: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refetch = async () => {
    try {
      const u = await me();
      setUser(u);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refetch();
  }, []);

  const doLogout = async () => {
    try {
      await logout();
    } catch {
      // ignore
    }
    setUser(null);
    setLoading(false);
    window.location.href = "/login";
  };

  return (
    <AuthContext.Provider value={{ user, loading, isAuthenticated: !!user, refetch, logout: doLogout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
