"use client";
import { ReactNode, useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "../context/AuthContext";

export default function AuthGuard({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    // redirect to login if not authenticated and not on auth pages
    if (user === null && !['/login', '/signup'].includes(pathname)) {
      router.push('/login');
    }
  }, [user, router, pathname]);

  if (!user) {
    // allow public access to login and signup pages
    if (['/login', '/signup'].includes(pathname)) {
      return <>{children}</>;
    }
    return <div>Loading...</div>;
  }
  return <>{children}</>;
}
