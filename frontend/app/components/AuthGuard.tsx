"use client";
import { ReactNode, useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "../context/AuthContext";

export default function AuthGuard({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    // If we've determined the user is not authenticated, redirect to login
    // Note: user === undefined means the auth status is still loading
    if (user === null && !['/login', '/signup'].includes(pathname)) {
      router.push('/login');
    }
  }, [user, router, pathname]);

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
