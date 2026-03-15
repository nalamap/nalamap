"use client";
import { ReactNode, useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "../context/AuthContext";

export default function AuthGuard({ children }: { children: ReactNode }) {
  const { user, authDisabled } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  // Skip auth guard in test environment to simplify E2E tests
  const isTestEnv = process.env.NEXT_PUBLIC_TEST;

  useEffect(() => {
    // Skip auth redirect in test environment or when auth is disabled
    if (isTestEnv || authDisabled) return;
    
    // If we've determined the user is not authenticated, redirect to login
    // Note: user === undefined means the auth status is still loading
    if (user === null && !['/login', '/signup'].includes(pathname)) {
      router.push('/login');
    }
  }, [user, router, pathname, isTestEnv, authDisabled]);

  // Skip auth guard in test environment or when backend auth is disabled
  if (isTestEnv || authDisabled) {
    return <>{children}</>;
  }

  // If auth status is loading, show a loader (don't redirect yet)
  if (user === undefined) {
    return <div>Loading...</div>;
  }

  if (user === null) {
    // allow public access to login and signup pages
    if (['/login', '/signup'].includes(pathname)) {
      return <>{children}</>;
    }
    return <div>Loading...</div>;
  }
  return <>{children}</>;
}
