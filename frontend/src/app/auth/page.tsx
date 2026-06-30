"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Mail, Lock, User, ArrowRight, Loader2, CheckCircle2 } from "lucide-react";
import { supabase } from "@/lib/supabase";

// Each bar has: [maxH, animName, durationMs, delayMs]
const BARS: [number, string, number, number][] = [
  [18, "vA", 2600,   0],  [34, "vB", 3100, 150],  [50, "vC", 2900,  70],
  [70, "vD", 2400, 250],  [88, "vA", 2650, 120],  [62, "vB", 3050, 210],
  [78, "vC", 2750,  50],  [44, "vD", 2550, 320],  [30, "vA", 3200, 160],
  [56, "vB", 2700,  90],  [74, "vC", 2950, 180],  [40, "vD", 2450, 360],
  [90, "vA", 2620,  70],  [50, "vB", 3150, 240],  [66, "vC", 2850, 130],
  [28, "vD", 2350, 280],  [82, "vA", 2700, 100],  [54, "vB", 3000, 190],
  [38, "vC", 2880,  60],  [70, "vD", 2500, 150],
];
const MOBILE_BARS = BARS.slice(0, 14);

export default function AuthPage() {
  const router = useRouter();
  const [isLogin, setIsLogin] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [isMobile, setIsMobile] = useState(false);

  // Override global overflow:hidden so auth page can scroll
  useEffect(() => {
    const targets = [document.documentElement, document.body, document.getElementById("__next")];
    targets.forEach(el => { if (el) el.style.overflow = "auto"; });
    return () => {
      targets.forEach(el => { if (el) el.style.overflow = ""; });
    };
  }, []);

  // JS-based responsive detection
  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 1024);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(null);
    try {
      if (isLogin) {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
        router.push("/");
      } else {
        const { data, error } = await supabase.auth.signUp({
          email,
          password,
          options: { 
            data: { display_name: displayName },
            emailRedirectTo: `${window.location.origin}/auth/confirm`
          },
        });
        if (error) throw error;
        
        if (data.session) {
          setSuccess("Account created! Redirecting...");
          setTimeout(() => router.push("/"), 1500);
        } else {
          setSuccess("Account created! Please check your email to verify your account.");
        }
      }
    } catch (err: any) {
      setError(err.message || "Authentication failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const renderLoader = () => (
    <div className={`absolute -inset-3 flex flex-col items-center justify-center gap-5 rounded-2xl z-50 animate-[fadeIn_0.25s_cubic-bezier(0.16,1,0.3,1)_both] backdrop-blur-[6px] ${isMobile ? "bg-[#09090b]/75" : "bg-white/75"}`}>
      <div className="absolute w-[140px] h-[140px] bg-[radial-gradient(circle,rgba(168,85,247,0.25)_0%,rgba(236,72,153,0)_70%)] blur-[15px] -z-10 animate-[pulseGlow_2s_ease-in-out_infinite]" />
      <div className="flex items-end gap-1.25 h-12">
        {[
          { anim: "pulseBar1", dur: "1.0s", delay: "0s" },
          { anim: "pulseBar2", dur: "1.2s", delay: "0.15s" },
          { anim: "pulseBar3", dur: "0.9s", delay: "0.05s" },
          { anim: "pulseBar4", dur: "1.1s", delay: "0.2s" },
          { anim: "pulseBar5", dur: "1.3s", delay: "0.1s" }
        ].map((bar, idx) => (
          <div key={idx} style={{
            animation: `${bar.anim} ${bar.dur} ease-in-out ${bar.delay} infinite`,
          }} className="w-1.25 h-12 bg-gradient-to-t from-[#6366f1] via-[#a855f7] to-[#ec4899] rounded-[2.5px] origin-bottom shadow-[0_0_10px_rgba(168,85,247,0.3)]" />
        ))}
      </div>
      <div className="flex flex-col items-center gap-1">
        <span className={`text-[12px] font-bold tracking-widest uppercase ${isMobile ? "text-[#fafafa]" : "text-[#09090b]"}`}>
          Verifying Identity
        </span>
        <span className={`text-[11px] tracking-normal ${isMobile ? "text-[#a1a1aa]" : "text-[#71717a]"}`}>
          Connecting to secure workspace...
        </span>
      </div>
    </div>
  );

  const renderFormFields = () => (
    <form
      key={isLogin ? "l" : "s"}
      onSubmit={handleSubmit}
      className="flex flex-col gap-4 animate-[fadeUp_0.3s_ease-out_both]"
    >
      {!isLogin && (
        <div className="flex flex-col gap-1.5">
          <label className={`text-[12px] font-medium ${isMobile ? "text-[#737373]" : "text-[#374151]"}`}>Full Name</label>
          <div className="relative flex items-center group">
            <User size={14} className="absolute left-[13px] pointer-events-none transition-colors duration-200 text-gray-400 group-focus-within:text-black dark:group-focus-within:text-white" />
            <input type="text" placeholder="John Smith" value={displayName}
              onChange={e => setDisplayName(e.target.value)}
              className={`w-full rounded-[10px] py-3 pl-10 pr-3.5 text-sm outline-none transition-all duration-200 border border-solid border-gray-200 focus:border-neutral-900 focus:shadow-[0_0_0_3px_rgba(0,0,0,0.08)] ${isMobile ? "bg-[#141414] text-[#e5e5e5] border-[#262626]" : "bg-[#fafafa] text-[#111827]"}`} />
          </div>
        </div>
      )}
      <div className="flex flex-col gap-1.5">
        <label className={`text-[12px] font-medium ${isMobile ? "text-[#737373]" : "text-[#374151]"}`}>Email Address</label>
        <div className="relative flex items-center group">
          <Mail size={14} className="absolute left-[13px] pointer-events-none transition-colors duration-200 text-gray-400 group-focus-within:text-black dark:group-focus-within:text-white" />
          <input type="email" required placeholder="you@company.com" value={email}
            onChange={e => setEmail(e.target.value)}
            className={`w-full rounded-[10px] py-3 pl-10 pr-3.5 text-sm outline-none transition-all duration-200 border border-solid border-gray-200 focus:border-neutral-900 focus:shadow-[0_0_0_3px_rgba(0,0,0,0.08)] ${isMobile ? "bg-[#141414] text-[#e5e5e5] border-[#262626]" : "bg-[#fafafa] text-[#111827]"}`} />
        </div>
      </div>
      <div className="flex flex-col gap-1.5">
        <div className="flex justify-between items-center">
          <label className={`text-[12px] font-medium ${isMobile ? "text-[#737373]" : "text-[#374151]"}`}>Password</label>
          {isLogin && <span className="text-[12px] text-[#111111] dark:text-[#a1a1aa] hover:underline cursor-pointer font-medium">Forgot password?</span>}
        </div>
        <div className="relative flex items-center group">
          <Lock size={14} className="absolute left-[13px] pointer-events-none transition-colors duration-200 text-gray-400 group-focus-within:text-black dark:group-focus-within:text-white" />
          <input type="password" required placeholder="••••••••••••" minLength={6} value={password}
            onChange={e => setPassword(e.target.value)}
            className={`w-full rounded-[10px] py-3 pl-10 pr-3.5 text-sm outline-none transition-all duration-200 border border-solid border-gray-200 focus:border-neutral-900 focus:shadow-[0_0_0_3px_rgba(0,0,0,0.08)] ${isMobile ? "bg-[#141414] text-[#e5e5e5] border-[#262626]" : "bg-[#fafafa] text-[#111827]"}`} />
        </div>
        {!isLogin && <p className={`text-[11px] margin-0 mt-0.5 ${isMobile ? "text-[#333]" : "text-gray-400"}`}>Minimum 6 characters.</p>}
      </div>
      <button type="submit" disabled={loading}
        className="w-full bg-[#111111] hover:bg-black text-white border-none rounded-[10px] py-3.5 px-5 text-sm font-semibold cursor-pointer flex items-center justify-center gap-2 transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed tracking-tight mt-2"
      >
        {loading
          ? <><Loader2 size={15} className="animate-spin" /><span>Please wait...</span></>
          : <><span>{isLogin ? "Sign In to Workspace" : "Create My Account"}</span><ArrowRight size={15} /></>}
      </button>
    </form>
  );

  // ─── Mobile Layout ───
  if (isMobile) {
    return (
      <>
        <style>{`
          @keyframes spin { to { transform: rotate(360deg); } }
          @keyframes vA {
            0%, 100% { transform: scaleY(0.15); }
            20% { transform: scaleY(0.85); }
            45% { transform: scaleY(0.30); }
            70% { transform: scaleY(0.95); }
          }
          @keyframes vB {
            0%, 100% { transform: scaleY(0.60); }
            25% { transform: scaleY(0.15); }
            50% { transform: scaleY(0.85); }
            75% { transform: scaleY(0.30); }
          }
          @keyframes vC {
            0%, 100% { transform: scaleY(0.30); }
            30% { transform: scaleY(0.90); }
            60% { transform: scaleY(0.20); }
            85% { transform: scaleY(0.70); }
          }
          @keyframes vD {
            0%, 100% { transform: scaleY(0.10); }
            25% { transform: scaleY(0.75); }
            55% { transform: scaleY(0.20); }
            80% { transform: scaleY(0.80); }
          }
          @keyframes fadeUp { from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)} }
          @keyframes fadeIn { from { opacity: 0; backdrop-filter: blur(0px); } to { opacity: 1; backdrop-filter: blur(6px); } }
          @keyframes pulseGlow {
            0%, 100% { transform: scale(1); opacity: 0.5; }
            50% { transform: scale(1.25); opacity: 0.8; }
          }
          @keyframes pulseBar1 { 0%, 100% { transform: scaleY(0.25); } 50% { transform: scaleY(1.0); } }
          @keyframes pulseBar2 { 0%, 100% { transform: scaleY(0.40); } 50% { transform: scaleY(0.85); } }
          @keyframes pulseBar3 { 0%, 100% { transform: scaleY(0.15); } 50% { transform: scaleY(0.95); } }
          @keyframes pulseBar4 { 0%, 100% { transform: scaleY(0.50); } 50% { transform: scaleY(0.70); } }
          @keyframes pulseBar5 { 0%, 100% { transform: scaleY(0.30); } 50% { transform: scaleY(1.0); } }
        `}</style>
        <div className="min-h-screen w-full bg-[#09090b] font-sans flex flex-col overflow-auto">

          {/* Hero */}
          <div className="px-6 pt-8 pb-7 border-b border-[#161616] flex flex-col gap-5">
            {/* Logo */}
            <div className="flex items-center gap-2.5">
              <div className="w-[30px] h-[30px] bg-white rounded-[7px] flex items-center justify-center text-[9px] font-extrabold text-[#09090b] tracking-wider">ACE</div>
              <span className="text-[13px] font-semibold text-[#a1a1aa]">Voice Controller</span>
            </div>
            {/* Headline */}
            <div>
              <h1 className="text-[32px] font-extrabold text-[#fafafa] leading-[1.1] tracking-tight mb-2.5">Voice<br />Commands.<br />Reimagined.</h1>
              <p className="text-[13px] text-[#52525b] leading-[1.65] m-0">Enterprise-grade voice automation for the modern workspace.</p>
            </div>
            {/* EQ Bars */}
            <div className="flex items-end gap-0.75 h-[36px]">
              {MOBILE_BARS.map(([h, anim, dur, delay], i) => (
                <div key={i} style={{
                  height: Math.round(h * 0.4),
                  animation: `${anim} ${dur}ms ease-in-out ${delay}ms infinite`,
                }} className="w-1 bg-white opacity-40 shrink-0 origin-bottom" />
              ))}
            </div>
            {/* Stats */}
            <div className="flex gap-7 pt-4 border-t border-[#18181b]">
              {[{ val: "<5s", lbl: "Response" }, { val: "99%", lbl: "Accuracy" }, { val: "256-bit", lbl: "Encrypted" }].map(({ val, lbl }) => (
                <div key={lbl} className="flex flex-col gap-0.5">
                  <span className="text-[16px] font-bold text-[#e4e4e7] tracking-tight">{val}</span>
                  <span className="text-[10px] text-[#525252] font-medium">{lbl}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Form */}
          <div className="px-6 pt-7 pb-12 flex-1">
            <h2 className="text-[22px] font-extrabold text-[#fafafa] tracking-tight mb-1.5">{isLogin ? "Welcome back." : "Create account."}</h2>
            <p className="text-[13px] text-[#52525b] mb-6 leading-relaxed">{isLogin ? "Sign in to your workspace." : "Set up your ACE workspace."}</p>

            <div className="relative">
              {/* Pill tabs */}
              <div className="flex gap-[5px] mb-5 bg-[#141414] p-1 rounded-[10px] border border-[#1c1c1c]">
                {["Sign In", "Sign Up"].map((label, i) => {
                  const active = (i === 0) === isLogin;
                  return (
                    <button key={label} onClick={() => { setIsLogin(i === 0); setError(null); setSuccess(null); }}
                      className={`flex-1 py-2.25 rounded-[7px] border-none text-[13px] font-semibold cursor-pointer transition-all duration-200 ${active ? "bg-[#1e1e1e] text-[#f5f5f5] shadow-[0_1px_4px_rgba(0,0,0,0.5)]" : "bg-transparent text-[#525252]"}`}>
                      {label}
                    </button>
                  );
                })}
              </div>

              {error && <div className="flex items-center px-3.5 py-2.75 rounded-lg text-[13px] mb-4 bg-red-500/8 text-[#f87171] border border-red-500/15"><span className="mr-1.5">⚠</span>{error}</div>}
              {success && <div className="flex items-center px-3.5 py-2.75 rounded-lg text-[13px] mb-4 bg-green-500/8 text-[#4ade80] border border-green-500/15"><CheckCircle2 size={14} className="mr-1.5" />{success}</div>}

              {renderFormFields()}

              {loading && renderLoader()}
            </div>
            <p className="text-[11px] text-[#52525b] text-center leading-[1.7] mt-5">By continuing you agree to our <span className="text-[#fafafa] underline cursor-pointer">Terms</span> &amp; <span className="text-[#fafafa] underline cursor-pointer">Privacy Policy</span>.</p>
          </div>
        </div>
      </>
    );
  }

  // ─── Desktop Layout ───
  return (
    <>
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes vA {
          0%, 100% { transform: scaleY(0.15); }
          20% { transform: scaleY(0.85); }
          45% { transform: scaleY(0.30); }
          70% { transform: scaleY(0.95); }
        }
        @keyframes vB {
          0%, 100% { transform: scaleY(0.60); }
          25% { transform: scaleY(0.15); }
          50% { transform: scaleY(0.85); }
          75% { transform: scaleY(0.30); }
        }
        @keyframes vC {
          0%, 100% { transform: scaleY(0.30); }
          30% { transform: scaleY(0.90); }
          60% { transform: scaleY(0.20); }
          85% { transform: scaleY(0.70); }
        }
        @keyframes vD {
          0%, 100% { transform: scaleY(0.10); }
          25% { transform: scaleY(0.75); }
          55% { transform: scaleY(0.20); }
          80% { transform: scaleY(0.80); }
        }
        @keyframes fadeUp { from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)} }
        @keyframes fadeIn { from { opacity: 0; backdrop-filter: blur(0px); } to { opacity: 1; backdrop-filter: blur(6px); } }
        @keyframes pulseGlow {
          0%, 100% { transform: scale(1); opacity: 0.5; }
          50% { transform: scale(1.25); opacity: 0.8; }
        }
        @keyframes pulseBar1 { 0%, 100% { transform: scaleY(0.25); } 50% { transform: scaleY(1.0); } }
        @keyframes pulseBar2 { 0%, 100% { transform: scaleY(0.40); } 50% { transform: scaleY(0.85); } }
        @keyframes pulseBar3 { 0%, 100% { transform: scaleY(0.15); } 50% { transform: scaleY(0.95); } }
        @keyframes pulseBar4 { 0%, 100% { transform: scaleY(0.50); } 50% { transform: scaleY(0.70); } }
        @keyframes pulseBar5 { 0%, 100% { transform: scaleY(0.30); } 50% { transform: scaleY(1.0); } }
      `}</style>
      <div className="flex min-h-screen w-full font-sans overflow-auto bg-[#09090b]">

        {/* Brand Panel */}
        <div className="w-[52%] min-h-screen bg-[#09090b] shrink-0 flex border-r border-[#18181b]">
          <div className="flex flex-col px-[52px] py-12 w-full justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 bg-white rounded-lg flex items-center justify-center text-[10px] font-extrabold text-[#09090b] tracking-wider">ACE</div>
              <span className="text-sm font-semibold text-[#a1a1aa]">Voice Controller</span>
            </div>
            <div className="flex-1 flex flex-col justify-center gap-5 py-10">
              <h1 className="text-[52px] font-extrabold text-[#fafafa] leading-[1.05] tracking-tight m-0">Voice<br />Commands.<br />Reimagined.</h1>
              <p className="text-[15px] text-[#52525b] leading-[1.7] m-0">The operating layer between your voice<br />and your entire digital workspace.</p>
            </div>
            <div className="flex items-end gap-1 h-24">
              {BARS.map(([h, anim, dur, delay], i) => (
                <div key={i} style={{
                  height: h,
                  animation: `${anim} ${dur}ms ease-in-out ${delay}ms infinite`,
                }} className="w-1.5 bg-white opacity-45 shrink-0 origin-bottom rounded-full" />
              ))}
            </div>
          </div>
        </div>

        {/* Form Panel */}
        <div className="flex-1 bg-white flex items-center justify-center px-10 py-12 overflow-y-auto">
          <div className="w-full max-w-[380px] flex flex-col">
            <h2 className="text-[26px] font-extrabold text-[#09090b] tracking-tight mb-2">{isLogin ? "Welcome back." : "Create account."}</h2>
            <p className="text-sm text-[#71717a] mb-7 leading-relaxed">{isLogin ? "Sign in to access your voice workspace." : "Set up your ACE workspace in seconds."}</p>

            <div className="relative">
              {/* Pills */}
              <div className="flex gap-[5px] mb-6 bg-[#f4f4f5] p-1 rounded-[10px]">
                {["Sign In", "Sign Up"].map((label, i) => {
                  const active = (i === 0) === isLogin;
                  return (
                    <button key={label} onClick={() => { setIsLogin(i === 0); setError(null); setSuccess(null); }}
                      className={`flex-1 py-2.25 rounded-[7px] border-none text-[13px] font-semibold cursor-pointer transition-all duration-200 ${active ? "bg-white text-[#09090b] shadow-[0_1px_3px_rgba(0,0,0,0.1)]" : "bg-transparent text-[#a1a1aa]"}`}>
                      {label}
                    </button>
                  );
                })}
              </div>

              {error && <div className="flex items-center px-3.5 py-2.75 rounded-lg text-[13px] mb-4 bg-red-50 text-red-600 border border-red-200"><span className="mr-1.5">⚠</span>{error}</div>}
              {success && <div className="flex items-center px-3.5 py-2.75 rounded-lg text-[13px] mb-4 bg-green-50 text-green-600 border border-green-200"><CheckCircle2 size={14} className="mr-1.5" />{success}</div>}

              {renderFormFields()}

              {loading && renderLoader()}
            </div>
            <p className="text-[11px] text-gray-400 text-center leading-[1.7] mt-5">By continuing you agree to our <span className="text-[#111111] underline cursor-pointer">Terms</span> &amp; <span className="text-[#111111] underline cursor-pointer">Privacy Policy</span>.</p>
          </div>
        </div>
      </div>
    </>
  );
}
