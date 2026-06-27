"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { supabase } from "@/lib/supabase";

export default function AuthConfirmPage() {
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("Verifying your email...");
  const searchParams = useSearchParams();
  const router = useRouter();

  useEffect(() => {
    const verifyToken = async () => {
      const errorStr = searchParams.get("error");
      const errorDesc = searchParams.get("error_description");
      
      if (errorStr) {
        setStatus("error");
        setMessage(errorDesc?.replace(/\+/g, ' ') || "Verification failed. The link may have expired.");
        return;
      }

      try {
        const { data, error } = await supabase.auth.getSession();
        if (error) throw error;

        setStatus("success");
        setMessage("Email verified successfully!");
      } catch (err: any) {
        setStatus("error");
        setMessage(err.message || "An error occurred during verification.");
      }
    };

    verifyToken();
  }, [searchParams]);

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col font-sans selection:bg-indigo-500/30 text-white relative overflow-hidden">
      
      {/* New Ambient Background Gradients */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,_rgba(56,189,248,0.15),_transparent_50%)] pointer-events-none" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_80%_80%,_rgba(129,140,248,0.15),_transparent_50%)] pointer-events-none" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[80vw] h-[80vw] bg-indigo-500/5 rounded-full blur-[100px] pointer-events-none" />

      {/* Header with Logo */}
      <div className="w-full p-6 flex items-center gap-3 absolute top-0 left-0 z-20">
        <div className="w-8 h-8 bg-white rounded-xl flex items-center justify-center text-[10px] font-extrabold text-slate-950 tracking-widest shadow-lg">
          ACE
        </div>
        <span className="text-sm font-medium text-slate-400 tracking-wide">Voice Controller</span>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center p-4 relative z-10">
        
        {/* New Glassmorphism Card Style */}
        <div className="w-full max-w-md p-8 md:p-10 rounded-[2rem] bg-white/5 backdrop-blur-2xl border border-white/10 shadow-[0_0_80px_-20px_rgba(0,0,0,0.7)] flex flex-col items-center text-center transition-all duration-500 relative">
          
          {/* Subtle top edge highlight for the card */}
          <div className="absolute top-0 inset-x-0 h-[1px] bg-gradient-to-r from-transparent via-white/30 to-transparent" />

          {/* Status Icon */}
          <div className="mb-8 relative flex justify-center items-center">
            {status === "loading" && (
              <>
                <div className="absolute w-24 h-24 rounded-full bg-blue-500/20 animate-ping duration-1000" />
                <div className="relative w-16 h-16 rounded-2xl bg-blue-500/10 flex items-center justify-center text-blue-400 border border-blue-500/30 shadow-[0_0_30px_rgba(59,130,246,0.3)]">
                  <Loader2 className="w-8 h-8 animate-spin" />
                </div>
              </>
            )}
            {status === "success" && (
              <>
                <div className="absolute w-24 h-24 rounded-full bg-teal-500/20 animate-pulse" />
                <div className="relative w-16 h-16 rounded-2xl bg-teal-500/10 flex items-center justify-center text-teal-400 border border-teal-500/30 shadow-[0_0_30px_rgba(20,184,166,0.3)] transform transition-transform hover:scale-105">
                  <CheckCircle2 className="w-8 h-8" />
                </div>
              </>
            )}
            {status === "error" && (
              <>
                <div className="absolute w-24 h-24 rounded-full bg-rose-500/10 animate-pulse" />
                <div className="relative w-16 h-16 rounded-2xl bg-rose-500/10 flex items-center justify-center text-rose-400 border border-rose-500/30 shadow-[0_0_30px_rgba(244,63,94,0.3)]">
                  <AlertCircle className="w-8 h-8" />
                </div>
              </>
            )}
          </div>

          {/* Title */}
          <h1 className="text-2xl md:text-3xl font-extrabold text-white mb-4 tracking-tight">
            {status === "loading" && "Verifying Email"}
            {status === "success" && "Verification Complete"}
            {status === "error" && "Verification Failed"}
          </h1>

          {/* Description */}
          <p className="text-sm md:text-base text-slate-300 mb-8 leading-relaxed max-w-[280px]">
            {message}
          </p>

          {/* Action Area */}
          {status === "success" && (
            <div className="w-full animate-in fade-in slide-in-from-bottom-4 duration-700">
              <div className="bg-slate-900/50 rounded-2xl p-5 border border-white/5 relative overflow-hidden shadow-inner">
                <p className="text-sm font-medium text-slate-300 leading-relaxed">
                  You can now safely <span className="text-white font-bold bg-white/10 px-2 py-0.5 rounded-md mx-1">close this tab</span> and return to the ACE desktop app to sign in.
                </p>
              </div>
            </div>
          )}

          {status === "error" && (
            <button 
              onClick={() => window.location.href = '/'}
              className="w-full py-3.5 px-6 bg-white text-slate-900 text-sm font-bold rounded-xl hover:bg-slate-100 transition-all duration-300 focus:outline-none focus:ring-4 focus:ring-white/20 shadow-xl active:scale-[0.98]"
            >
              Return to Application
            </button>
          )}
        </div>
      </div>
    </div>
  );
}