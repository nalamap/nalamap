"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../context/AuthContext";
import { getApiBase } from "../utils/apiBase";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [providers, setProviders] = useState<Array<{ name: string; issuer: string }>>([]);
  const apiBase = getApiBase();

  useEffect(() => {
    async function loadProviders() {
      try {
        const res = await fetch(`${apiBase}/auth/oidc/providers`);
        if (!res.ok) return;
        const data = await res.json();
        setProviders(data);
      } catch {
        // ignore provider fetch errors to keep password login available
      }
    }
    loadProviders();
  }, [apiBase]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await login(email, password);
      router.push('/map');
    } catch (err) {
      setError("Invalid credentials");
    }
  };

  return (
    <main className="obsidian-auth-shell">
      <div className="obsidian-auth-card space-y-6">
        <div className="space-y-3">
          <p className="obsidian-kicker">NaLaMap Access</p>
          <h1 className="obsidian-auth-title">Login</h1>
          <p className="obsidian-auth-copy">
            Enter your account credentials to continue into the geospatial workspace.
          </p>
        </div>
        {error && <div className="obsidian-note obsidian-note-danger text-sm">{error}</div>}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="obsidian-form-field">
            <label className="obsidian-form-label">Email</label>
            <input
              type="email"
              name="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="obsidian-input"
              required
            />
          </div>
          <div className="obsidian-form-field">
            <label className="obsidian-form-label">Password</label>
            <input
              type="password"
              name="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="obsidian-input"
              required
            />
          </div>
          <button
            type="submit"
            className="obsidian-button-primary w-full"
          >
            Login
          </button>
        </form>
        {providers.length > 0 && (
          <div className="space-y-3">
            <div className="obsidian-kicker">Federated Sign-In</div>
            <div className="space-y-2">
              {providers.map((p) => (
                <button
                  key={p.name}
                  onClick={() => {
                    const redirect = `${window.location.origin}/map`;
                    const url = `${apiBase}/auth/oidc/login?provider=${p.name}&redirect=${encodeURIComponent(
                      redirect
                    )}`;
                    window.location.href = url;
                  }}
                  className="obsidian-button-ghost w-full"
                >
                  Continue with {p.name.charAt(0).toUpperCase() + p.name.slice(1)}
                </button>
              ))}
            </div>
          </div>
        )}
        <p className="text-sm obsidian-status-muted">
          Don&apos;t have an account?{" "}
          <a href="/signup" className="obsidian-link">
            Sign up
          </a>
        </p>
      </div>
    </main>
  );
}
