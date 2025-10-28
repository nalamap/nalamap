"use client";
import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { getApiBase } from "../utils/apiBase";

interface User {
  id: string;
  email: string;
  display_name?: string;
}

interface AuthContextValue {
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, displayName: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const apiBase = getApiBase();

  // try to fetch current user on mount
  useEffect(() => {
    async function fetchMe() {
      try {
        const res = await fetch(`${apiBase}/auth/me`, { credentials: "include" });
        if (res.ok) {
          const data = await res.json();
          setUser(data);
        }
      } catch {
        setUser(null);
      }
    }
    fetchMe();
  }, []);

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

  function logout() {
    // clear cookie on server
    fetch(`${apiBase}/auth/logout`, { method: "POST", credentials: "include" });
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, login, signup, logout }}>
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
