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
    // When Supabase redirects here from an email link, it usually includes a hash containing the access token
    // or an error in the query params. We can use supabase.auth.getSession() to let the client library
    // parse the URL hash and establish the session.
    
    const verifyToken = async () => {
      // Check for explicit error in URL (e.g. ?error=access_denied&error_description=...)
      const errorStr = searchParams.get("error");
      const errorDesc = searchParams.get("error_description");
      
      if (errorStr) {
        setStatus("error");
        setMessage(errorDesc?.replace(/\+/g, ' ') || "Verification failed. The link may have expired.");
        return;
      }

      try {
        const { data, error } = await supabase.auth.getSession();
        
        if (error) {
          throw error;
        }

        // Even if there's no session immediately, if there's no error, Supabase has processed the verification.
        // The user's email is confirmed in the backend.
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
    <div className="min-h-screen bg-[#09090b] flex flex-col font-sans selection:bg-white/10 text-white relative overflow-hidden">
      
      {/* Background Gradients */}
      <div className="absolute top-[-10%] left-[-10%] w-[40vw] h-[40vw] bg-emerald-500/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[40vw] h-[40vw] bg-blue-500/10 rounded-full blur-[120px] pointer-events-none" />

      {/* Header with Logo */}
      <div className="w-full p-6 md:p-8 flex items-center gap-3 absolute top-0 left-0 z-20">
        <div className="w-8 h-8 bg-white rounded-lg flex items-center justify-center text-[10px] font-extrabold text-[#09090b] tracking-widest">
          ACE
        </div>
        <span className="text-sm font-semibold text-zinc-400">Voice Controller</span>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center p-6 relative z-10">
        <div className="w-full max-w-lg p-10 md:p-14 rounded-[32px] bg-[#121214]/80 backdrop-blur-2xl border border-white/5 shadow-[0_30px_100px_-20px_rgba(0,0,0,0.5)] flex flex-col items-center text-center transition-all duration-500">
          
          {/* Status Icon */}
          <div className="mb-10 relative flex justify-center items-center">
            {status === "loading" && (
              <>
                <div className="absolute w-24 h-24 rounded-full bg-blue-500/20 animate-ping duration-1000" />
                <div className="relative w-20 h-20 rounded-full bg-blue-500/10 flex items-center justify-center text-blue-400 border border-blue-500/20 shadow-[0_0_40px_rgba(59,130,246,0.3)]">
                  <Loader2 className="w-10 h-10 animate-spin" />
                </div>
              </>
            )}
            {status === "success" && (
              <>
                <div className="absolute w-24 h-24 rounded-full bg-emerald-500/20 animate-pulse" />
                <div className="relative w-20 h-20 rounded-full bg-emerald-500/10 flex items-center justify-center text-emerald-400 border border-emerald-500/20 shadow-[0_0_40px_rgba(16,185,129,0.3)]">
                  <CheckCircle2 className="w-10 h-10" />
                </div>
              </>
            )}
            {status === "error" && (
              <>
                <div className="absolute w-24 h-24 rounded-full bg-red-500/10" />
                <div className="relative w-20 h-20 rounded-full bg-red-500/10 flex items-center justify-center text-red-400 border border-red-500/20 shadow-[0_0_40px_rgba(239,68,68,0.2)]">
                  <AlertCircle className="w-10 h-10" />
                </div>
              </>
            )}
          </div>

          {/* Title */}
          <h1 className="text-3xl md:text-4xl font-extrabold text-gray-50 mb-5 tracking-tight">
            {status === "loading" && "Verifying your email"}
            {status === "success" && "Verification Complete"}
            {status === "error" && "Verification Failed"}
          </h1>

          {/* Description */}
          <p className="text-base md:text-lg text-zinc-400 mb-10 leading-relaxed max-w-sm">
            {message}
          </p>

          {/* Action Area */}
          {status === "success" && (
            <div className="w-full flex flex-col gap-4 animate-in fade-in slide-in-from-bottom-4 duration-700">
              <div className="bg-[#18181b] rounded-2xl p-6 md:p-8 border border-white/5 relative overflow-hidden group shadow-inner">
                <div className="absolute inset-0 bg-gradient-to-r from-emerald-500/0 via-emerald-500/5 to-emerald-500/0 opacity-0 group-hover:opacity-100 transition-opacity duration-700" />
                <p className="text-sm md:text-base font-medium text-zinc-300 leading-relaxed relative z-10">
                  You can now safely <span className="text-white font-bold tracking-wide">close this browser tab</span> and return to the ACE desktop application to sign in.
                </p>
              </div>
            </div>
          )}

          {status === "error" && (
            <button 
              onClick={() => window.location.href = '/'}
              className="w-full py-4 px-6 bg-white text-black text-base font-bold rounded-xl hover:bg-gray-100 hover:scale-[1.02] transition-all duration-300 focus:outline-none focus:ring-4 focus:ring-white/20 active:scale-[0.98] shadow-lg"
            >
              Return to Application
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
