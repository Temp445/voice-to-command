"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuthStore } from "@/store/authStore";
import { Loader2 } from "lucide-react";
import { useSupabaseSync } from "@/hooks/useSupabaseSync";

export function AuthWrapper({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { session, loading, initializeAuth } = useAuthStore();

  // Activate realtime background sync
  useSupabaseSync();

  useEffect(() => {
    initializeAuth();
  }, [initializeAuth]);

  const isAuthPage = pathname === "/auth" || pathname === "/auth/";

  useEffect(() => {
    if (!loading) {
      if (!session && !isAuthPage) {
        window.location.href = "/auth";
      } else if (session && isAuthPage) {
        router.push("/");
      }
    }
  }, [session, loading, pathname, router, isAuthPage]);

  // Show a loading screen while auth state is resolving
  if (loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-[#09090b] font-sans gap-4 relative overflow-hidden">
        {/* Subtle glow */}
        <div className="absolute w-[120px] h-[120px] bg-purple-500/5 blur-[30px] -z-10" />

        {/* Minimal rotating gradient ring */}
        <div className="w-7 h-7 rounded-full border-2 border-zinc-800 border-t-zinc-400 animate-spin" />

        {/* Minimal description */}
        <span className="text-[11px] font-medium text-zinc-500 tracking-wider uppercase animate-pulse">
          Authenticating
        </span>
      </div>
    );
  }

  // Prevent rendering protected content briefly before redirect
  if (!session && !isAuthPage) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-[#09090b] font-sans gap-4 relative overflow-hidden">
        {/* Subtle glow */}
        <div className="absolute w-[120px] h-[120px] bg-purple-500/5 blur-[30px] -z-10" />

        {/* Minimal rotating gradient ring */}
        <div className="w-7 h-7 rounded-full border-2 border-zinc-800 border-t-zinc-400 animate-spin" />

        {/* Minimal description */}
        <span className="text-[11px] font-medium text-zinc-500 tracking-wider uppercase animate-pulse">
          Redirecting
        </span>
      </div>
    );
  }

  return <>{children}</>;
}
