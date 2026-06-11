"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuthStore } from "@/store/authStore";
import { Loader2 } from "lucide-react";

export function AuthWrapper({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { session, loading, initializeAuth } = useAuthStore();

  useEffect(() => {
    initializeAuth();
  }, [initializeAuth]);

  const isAuthPage = pathname === "/auth" || pathname === "/auth/";

  useEffect(() => {
    if (!loading) {
      if (!session && !isAuthPage) {
        router.push("/auth");
      } else if (session && isAuthPage) {
        router.push("/");
      }
    }
  }, [session, loading, pathname, router, isAuthPage]);

  // Show a loading screen while auth state is resolving
  if (loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-zinc-950">
        <Loader2 className="w-8 h-8 text-blue-500 animate-spin mb-4" />
        <p className="text-zinc-400">Authenticating...</p>
      </div>
    );
  }

  // Prevent rendering protected content briefly before redirect
  if (!session && !isAuthPage) {
    return null;
  }

  return <>{children}</>;
}
