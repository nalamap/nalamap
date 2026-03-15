"use client";
import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { getApiBase } from "../utils/apiBase";

interface User {
  id: string;
  email: string;
  display_name?: string;
}

interface AuthContextValue {
  // undefined = loading, null = not authenticated, User = authenticated
  user: User | null | undefined;
  /** True when the backend reports AUTH_ENABLED=false */
  authDisabled: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, displayName: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  // undefined = loading, null = not authenticated, User = authenticated
  const [user, setUser] = useState<User | null | undefined>(undefined);
  const [authDisabled, setAuthDisabled] = useState(false);
  const apiBase = getApiBase();

  // try to fetch current user on mount
  useEffect(() => {
    async function fetchMe() {
      try {
        // Check if auth is disabled on the backend
        const statusRes = await fetch(`${apiBase}/auth/status`);
        if (statusRes.ok) {
          const statusData = await statusRes.json();
          if (statusData.auth_enabled === false) {
            setAuthDisabled(true);
          }
        }
      } catch {
        // ignore – fall through to normal auth check
      }

      try {
        const res = await fetch(`${apiBase}/auth/me`, { credentials: "include" });
        if (res.ok) {
          const data = await res.json();
          setUser(data);
          return;
        }
      } catch {
        // ignored - treat as not authenticated
      }
      setUser(null);
    }
    fetchMe();
  }, [apiBase]);

  async function login(email: string, password: string) {
    const res = await fetch(`${apiBase}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) throw new Error("Login failed");
    const data = await res.json();
    setUser(data.user);
  }

  async function signup(email: string, password: string, displayName: string) {
    const res = await fetch(`${apiBase}/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ email, password, display_name: displayName }),
    });
    if (!res.ok) throw new Error("Sign-up failed");
    const data = await res.json();
    setUser(data.user);
  }

  async function logout() {
    // clear cookie on server
    try {
      await fetch(`${apiBase}/auth/logout`, { method: "POST", credentials: "include" });
    } catch (err) {
      // best-effort; still clear local auth state
    }
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, authDisabled, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (ctx === undefined) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
