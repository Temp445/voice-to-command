"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { supabase } from "@/lib/supabase";

export default function AuthConfirmPage() {
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("Verifying your email address…");
  const searchParams = useSearchParams();
  const router = useRouter();

  useEffect(() => {
    const verifyToken = async () => {
      const errorStr = searchParams.get("error");
      const errorDesc = searchParams.get("error_description");

      if (errorStr) {
        setStatus("error");
        setMessage(
          errorDesc?.replace(/\+/g, " ") ||
            "This link may have expired or already been used. Please request a new verification email."
        );
        return;
      }

      try {
        const { data, error } = await supabase.auth.getSession();
        if (error) throw error;
        setStatus("success");
        setMessage("Your email has been confirmed and your account is ready.");
      } catch (err: any) {
        setStatus("error");
        setMessage(
          err.message ||
            "This link may have expired or already been used. Please request a new verification email."
        );
      }
    };

    verifyToken();
  }, [searchParams]);

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#09090b] font-sans text-white selection:bg-white/10 flex flex-col items-center justify-center p-6">

      {/* Background Gradients */}
      {/* <div className="pointer-events-none absolute -left-[15%] -top-[15%] h-[45vw] w-[45vw] min-h-[200px] min-w-[200px] rounded-full bg-emerald-500/10 blur-[120px]" />
      <div className="pointer-events-none absolute -bottom-[15%] -right-[15%] h-[45vw] w-[45vw] min-h-[200px] min-w-[200px] rounded-full bg-blue-500/10 blur-[120px]" /> */}

      {/* Header */}
      <div className="absolute left-0 top-0 z-20 flex w-full items-center gap-3 p-6 md:p-8">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white text-[9px] font-black tracking-widest text-[#09090b]">
          ACE
        </div>
        <span className="text-sm font-semibold text-zinc-500">Voice Controller</span>
      </div>

      {/* Card */}
      <div className="relative z-10 flex w-full max-w-md flex-col items-center rounded-[28px] border border-white/[0.06] bg-[#121214]/85 p-10 text-center shadow-[0_32px_80px_-20px_rgba(0,0,0,0.6)] backdrop-blur-2xl md:p-14">

        {/* Status Icon */}
        <div className="relative mb-8 flex h-[88px] w-[88px] items-center justify-center">
          {status === "loading" && (
            <>
              <div className="absolute inset-0 animate-ping rounded-full bg-blue-500/15 [animation-duration:1.4s]" />
              <div className="relative z-10 flex h-[72px] w-[72px] items-center justify-center rounded-full border border-blue-500/25 bg-blue-500/10 text-blue-400 shadow-[0_0_40px_rgba(59,130,246,0.2)]">
                <Loader2 className="h-9 w-9 animate-spin" />
              </div>
            </>
          )}
          {status === "success" && (
            <>
              <div className="absolute inset-0 animate-pulse rounded-full bg-emerald-500/15 [animation-duration:2s]" />
              <div className="relative z-10 flex h-[72px] w-[72px] items-center justify-center rounded-full border border-emerald-500/25 bg-emerald-500/10 text-emerald-400 shadow-[0_0_40px_rgba(16,185,129,0.25)]">
                <CheckCircle2 className="h-9 w-9" />
              </div>
            </>
          )}
          {status === "error" && (
            <>
              <div className="absolute inset-0 rounded-full bg-red-500/8" />
              <div className="relative z-10 flex h-[72px] w-[72px] items-center justify-center rounded-full border border-red-500/20 bg-red-500/10 text-red-400 shadow-[0_0_32px_rgba(239,68,68,0.15)]">
                <AlertCircle className="h-9 w-9" />
              </div>
            </>
          )}
        </div>

        {/* Title */}
        <h1 className="mb-3 text-2xl font-extrabold tracking-tight text-zinc-50 md:text-[28px]">
          {status === "loading" && "Verifying your email"}
          {status === "success" && "Verification complete"}
          {status === "error" && "Verification failed"}
        </h1>

        {/* Description */}
        <p className="mb-8 max-w-[280px] text-sm leading-relaxed text-zinc-500 md:text-[15px]">
          {message}
        </p>

        {/* Action Area */}
        {status === "success" && (
          <div className="w-full animate-in fade-in slide-in-from-bottom-4 duration-700">
            {/* Badge */}
            <div className="mb-4 flex justify-center">
              <span className="inline-flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-400">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                Email verified
              </span>
            </div>
            {/* Info box */}
            <div className="relative overflow-hidden rounded-2xl border border-white/[0.05] bg-[#18181b] p-5 shadow-inner">
              <p className="relative z-10 text-sm leading-relaxed text-zinc-400 md:text-[15px]">
                You can now safely{" "}
                <span className="font-bold tracking-wide text-white">close this tab</span>{" "}
                and return to the ACE desktop application to sign in.
              </p>
            </div>
          </div>
        )}

        {status === "error" && (
          <button
            onClick={() => (window.location.href = "/")}
            className="w-full animate-in fade-in slide-in-from-bottom-4 rounded-xl bg-white py-[14px] px-6 text-[15px] font-bold text-black shadow-lg duration-700 transition-all hover:scale-[1.02] hover:bg-zinc-100 focus:outline-none focus:ring-4 focus:ring-white/20 active:scale-[0.98]"
          >
            Return to application
          </button>
        )}
      </div>
    </div>
  );
}