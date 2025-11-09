"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../context/AuthContext";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

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
    <div className="max-w-md mx-auto mt-16 p-4 border border-primary-300 rounded">
      <h1 className="text-xl font-semibold mb-4">Login</h1>
      {error && <div className="text-danger-600 mb-2">{error}</div>}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label>Email</label>
          <input
            type="email"
            name="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full border border-primary-300 p-2 rounded"
            required
          />
        </div>
        <div>
          <label>Password</label>
          <input
            type="password"
            name="password"
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
          Login
        </button>
      </form>
      <p className="mt-4 text-sm">
        Don't have an account?{' '}
        <a href="/signup" className="text-second-primary-600 hover:text-second-primary-700">
          Sign up
        </a>
      </p>
    </div>
  );
}
