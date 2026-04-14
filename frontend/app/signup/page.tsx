"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../context/AuthContext";
import { getApiBase } from "../utils/apiBase";

export default function SignupPage() {
  const router = useRouter();
  const { signup } = useAuth();
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
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
        // ignore provider fetch errors to keep password signup available
      }
    }
    loadProviders();
  }, [apiBase]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await signup(email, password, displayName);
      router.push('/map');
    } catch {
      setError("Sign-up failed");
    }
  };

  return (
    <main className="obsidian-auth-shell">
      <div className="obsidian-auth-card space-y-6">
        <div className="space-y-3">
          <p className="obsidian-kicker">NaLaMap Access</p>
          <h1 className="obsidian-auth-title">Sign Up</h1>
          <p className="obsidian-auth-copy">
            Create your account to start building and analyzing geospatial workspaces.
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
            <label className="obsidian-form-label">Display Name</label>
            <input
              type="text"
              name="displayName"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
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
            Sign Up
          </button>
        </form>
        {providers.length > 0 && (
          <div className="space-y-3">
            <div className="obsidian-kicker">Federated Sign-Up</div>
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
          Already have an account?{" "}
          <a href="/login" className="obsidian-link">
            Login
          </a>
        </p>
      </div>
    </main>
  );
}
