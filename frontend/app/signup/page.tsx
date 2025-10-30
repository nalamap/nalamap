"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../context/AuthContext";

export default function SignupPage() {
  const router = useRouter();
  const { signup } = useAuth();
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await signup(email, password, displayName);
      router.push('/');
    } catch {
      setError("Sign-up failed");
    }
  };

  return (
    <div className="max-w-md mx-auto mt-16 p-4 border border-primary-300 rounded">
      <h1 className="text-xl font-semibold mb-4">Sign Up</h1>
      {error && <div className="text-danger-600 mb-2">{error}</div>}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label>Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full border border-primary-300 p-2 rounded"
            required
          />
        </div>
        <div>
          <label>Display Name</label>
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className="w-full border border-primary-300 p-2 rounded"
            required
          />
        </div>
        <div>
          <label>Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full border border-primary-300 p-2 rounded"
            required
          />
        </div>
        <button
          type="submit"
          className="w-full bg-second-primary-600 text-neutral-50 p-2 rounded hover:bg-second-primary-700"
        >
          Sign Up
        </button>
      </form>
      <p className="mt-4 text-sm">
        Already have an account?{' '}
        <a href="/login" className="text-second-primary-600 hover:text-second-primary-700">
          Login
        </a>
      </p>
    </div>
  );
}
