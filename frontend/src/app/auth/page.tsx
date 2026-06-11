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
const BAR_HEIGHTS = BARS.map(b => b[0]);
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
  const [focusedField, setFocusedField] = useState<string | null>(null);
  const [isMobile, setIsMobile] = useState(false);

  // Override global overflow:hidden so auth page can scroll
  useEffect(() => {
    const targets = [document.documentElement, document.body, document.getElementById("__next")];
    targets.forEach(el => { if (el) el.style.overflow = "auto"; });
    return () => {
      targets.forEach(el => { if (el) el.style.overflow = ""; });
    };
  }, []);

  // JS-based responsive detection — bypasses CSS overflow:hidden issues
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
        const { error } = await supabase.auth.signUp({
          email,
          password,
          options: { data: { display_name: displayName } },
        });
        if (error) throw error;
        setSuccess("Account created! Redirecting...");
        setTimeout(() => router.push("/"), 1500);
      }
    } catch (err: any) {
      setError(err.message || "Authentication failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const inputBorder = (field: string) =>
    focusedField === field ? "#111111" : isMobile ? "#262626" : "#e5e7eb";
  const inputShadow = (field: string) =>
    focusedField === field ? "0 0 0 3px rgba(0,0,0,0.08)" : "none";

  // ─── Shared form fields ───
  const renderFormFields = () => (
    <form
      key={isLogin ? "l" : "s"}
      onSubmit={handleSubmit}
      style={{ display: "flex", flexDirection: "column", gap: 16, animation: "fadeUp 0.3s ease-out both" }}
    >
      {!isLogin && (
        <div style={fs.group}>
          <label style={{ ...fs.label, color: isMobile ? "#737373" : "#374151" }}>Full Name</label>
          <div style={fs.wrap}>
            <User size={14} color={focusedField === "name" ? "#111111" : isMobile ? "#404040" : "#9ca3af"} style={fs.icon} />
            <input type="text" placeholder="John Smith" value={displayName}
              onChange={e => setDisplayName(e.target.value)}
              onFocus={() => setFocusedField("name")} onBlur={() => setFocusedField(null)}
              style={{ ...fs.input, ...(isMobile ? fs.darkInput : fs.lightInput), borderColor: inputBorder("name"), boxShadow: inputShadow("name") }} />
          </div>
        </div>
      )}
      <div style={fs.group}>
        <label style={{ ...fs.label, color: isMobile ? "#737373" : "#374151" }}>Email Address</label>
        <div style={fs.wrap}>
          <Mail size={14} color={focusedField === "email" ? "#111111" : isMobile ? "#404040" : "#9ca3af"} style={fs.icon} />
          <input type="email" required placeholder="you@company.com" value={email}
            onChange={e => setEmail(e.target.value)}
            onFocus={() => setFocusedField("email")} onBlur={() => setFocusedField(null)}
            style={{ ...fs.input, ...(isMobile ? fs.darkInput : fs.lightInput), borderColor: inputBorder("email"), boxShadow: inputShadow("email") }} />
        </div>
      </div>
      <div style={fs.group}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <label style={{ ...fs.label, color: isMobile ? "#737373" : "#374151" }}>Password</label>
          {isLogin && <span style={{ fontSize: 12, color: "#111111", cursor: "pointer", fontWeight: 500 }}>Forgot password?</span>}
        </div>
        <div style={fs.wrap}>
          <Lock size={14} color={focusedField === "password" ? "#111111" : isMobile ? "#404040" : "#9ca3af"} style={fs.icon} />
          <input type="password" required placeholder="••••••••••••" minLength={6} value={password}
            onChange={e => setPassword(e.target.value)}
            onFocus={() => setFocusedField("password")} onBlur={() => setFocusedField(null)}
            style={{ ...fs.input, ...(isMobile ? fs.darkInput : fs.lightInput), borderColor: inputBorder("password"), boxShadow: inputShadow("password") }} />
        </div>
        {!isLogin && <p style={{ fontSize: 11, color: isMobile ? "#333" : "#9ca3af", margin: "3px 0 0" }}>Minimum 6 characters.</p>}
      </div>
      <button type="submit" disabled={loading}
        style={{ ...fs.submitBtn, marginTop: 8 }}
        onMouseEnter={e => { if (!loading) e.currentTarget.style.background = "#000000"; }}
        onMouseLeave={e => { if (!loading) e.currentTarget.style.background = "#111111"; }}>
        {loading
          ? <><Loader2 size={15} style={{ animation: "spin 1s linear infinite" }} /><span>Please wait...</span></>
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
          /* 4 unique smooth voice frequency animations */
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
        `}</style>
        <div style={{ minHeight: "100vh", width: "100%", background: "#09090b", fontFamily: "Inter, system-ui, sans-serif", display: "flex", flexDirection: "column", overflow: "auto" }}>

          {/* Hero */}
          <div style={{ padding: "32px 24px 28px", borderBottom: "1px solid #161616", display: "flex", flexDirection: "column", gap: 20 }}>
            {/* Logo */}
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{ width: 30, height: 30, background: "#ffffff", borderRadius: 7, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 9, fontWeight: 800, color: "#09090b", letterSpacing: "0.1em" }}>ACE</div>
              <span style={{ fontSize: 13, fontWeight: 600, color: "#a1a1aa" }}>Voice Controller</span>
            </div>
            {/* Headline */}
            <div>
              <h1 style={{ fontSize: 32, fontWeight: 800, color: "#fafafa", lineHeight: 1.1, letterSpacing: "-0.03em", margin: "0 0 10px" }}>Voice<br />Commands.<br />Reimagined.</h1>
              <p style={{ fontSize: 13, color: "#52525b", lineHeight: 1.65, margin: 0 }}>Enterprise-grade voice automation for the modern workspace.</p>
            </div>
            {/* EQ Bars */}
            <div style={{ display: "flex", alignItems: "flex-end", gap: 3, height: 36 }}>
              {MOBILE_BARS.map(([h, anim, dur, delay], i) => (
                <div key={i} style={{ width: 4, height: Math.round(h * 0.4), borderRadius: 2, background: "#ffffff", opacity: 0.4, flexShrink: 0, animation: `${anim} ${dur}ms ease-in-out ${delay}ms infinite`, transformOrigin: "bottom" }} />
              ))}
            </div>
            {/* Stats */}
            <div style={{ display: "flex", gap: 28, paddingTop: 16, borderTop: "1px solid #18181b" }}>
              {[{ val: "<5s", lbl: "Response" }, { val: "99%", lbl: "Accuracy" }, { val: "256-bit", lbl: "Encrypted" }].map(({ val, lbl }) => (
                <div key={lbl} style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  <span style={{ fontSize: 16, fontWeight: 700, color: "#e4e4e7", letterSpacing: "-0.02em" }}>{val}</span>
                  <span style={{ fontSize: 10, color: "#525252", fontWeight: 500 }}>{lbl}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Form */}
          <div style={{ padding: "28px 24px 48px", flex: 1 }}>
            <h2 style={{ fontSize: 22, fontWeight: 800, color: "#fafafa", letterSpacing: "-0.03em", margin: "0 0 6px" }}>{isLogin ? "Welcome back." : "Create account."}</h2>
            <p style={{ fontSize: 13, color: "#52525b", margin: "0 0 24px", lineHeight: 1.6 }}>{isLogin ? "Sign in to your workspace." : "Set up your ACE workspace."}</p>

            {/* Pill tabs */}
            <div style={{ display: "flex", gap: 5, marginBottom: 20, background: "#141414", padding: 4, borderRadius: 10, border: "1px solid #1c1c1c" }}>
              {["Sign In", "Sign Up"].map((label, i) => {
                const active = (i === 0) === isLogin;
                return (
                  <button key={label} onClick={() => { setIsLogin(i === 0); setError(null); setSuccess(null); }}
                    style={{ flex: 1, padding: "9px 0", borderRadius: 7, border: "none", fontSize: 13, fontWeight: 600, cursor: "pointer", background: active ? "#1e1e1e" : "transparent", color: active ? "#f5f5f5" : "#525252", boxShadow: active ? "0 1px 4px rgba(0,0,0,0.5)" : "none", fontFamily: "Inter, system-ui, sans-serif", transition: "all 0.2s" }}>
                    {label}
                  </button>
                );
              })}
            </div>

            {error && <div style={{ display: "flex", alignItems: "center", padding: "11px 14px", borderRadius: 8, fontSize: 13, marginBottom: 16, background: "rgba(239,68,68,0.08)", color: "#f87171", border: "1px solid rgba(239,68,68,0.15)" }}><span style={{ marginRight: 6 }}>⚠</span>{error}</div>}
            {success && <div style={{ display: "flex", alignItems: "center", padding: "11px 14px", borderRadius: 8, fontSize: 13, marginBottom: 16, background: "rgba(34,197,94,0.08)", color: "#4ade80", border: "1px solid rgba(34,197,94,0.15)" }}><CheckCircle2 size={14} style={{ marginRight: 6 }} />{success}</div>}

            {renderFormFields()}
            <p style={{ fontSize: 11, color: "#2d2d2d", textAlign: "center", lineHeight: 1.7, margin: "20px 0 0" }}>By continuing you agree to our <span style={{ color: "#111111", textDecoration: "underline", cursor: "pointer" }}>Terms</span> &amp; <span style={{ color: "#111111", textDecoration: "underline", cursor: "pointer" }}>Privacy Policy</span>.</p>
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
        /* 4 unique smooth voice frequency animations */
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
      `}</style>
      <div style={{ display: "flex", minHeight: "100vh", width: "100%", fontFamily: "Inter, system-ui, sans-serif", overflow: "auto", background: "#09090b" }}>

        {/* Brand Panel */}
        <div style={{ width: "52%", minHeight: "100vh", background: "#09090b", flexShrink: 0, display: "flex", borderRight: "1px solid #18181b" }}>
          <div style={{ display: "flex", flexDirection: "column", padding: "48px 52px", width: "100%", justifyContent: "space-between" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{ width: 32, height: 32, background: "#ffffff", borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, fontWeight: 800, color: "#09090b", letterSpacing: "0.1em" }}>ACE</div>
              <span style={{ fontSize: 14, fontWeight: 600, color: "#a1a1aa" }}>Voice Controller</span>
            </div>
            <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", gap: 20, padding: "40px 0" }}>
              <h1 style={{ fontSize: 52, fontWeight: 800, color: "#fafafa", lineHeight: 1.05, letterSpacing: "-0.04em", margin: 0 }}>Voice<br />Commands.<br />Reimagined.</h1>
              <p style={{ fontSize: 15, color: "#52525b", lineHeight: 1.7, margin: 0 }}>The operating layer between your voice<br />and your entire digital workspace.</p>
            </div>
            <div style={{ display: "flex", alignItems: "flex-end", gap: 4, height: 96 }}>
              {BARS.map(([h, anim, dur, delay], i) => (
                <div key={i} style={{ width: 6, height: h, borderRadius: 3, background: "#ffffff", opacity: 0.45, flexShrink: 0, animation: `${anim} ${dur}ms ease-in-out ${delay}ms infinite`, transformOrigin: "bottom" }} />
              ))}
            </div>
            {/* <div style={{ display: "flex", gap: 36, paddingTop: 28, borderTop: "1px solid #18181b", marginTop: 20 }}>
              {[{ val: "<5s", lbl: "Response Time" }, { val: "99%", lbl: "Accuracy" }, { val: "256-bit", lbl: "Encryption" }].map(({ val, lbl }) => (
                <div key={lbl} style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                  <span style={{ fontSize: 18, fontWeight: 700, color: "#e4e4e7", letterSpacing: "-0.02em" }}>{val}</span>
                  <span style={{ fontSize: 11, color: "#52525b", fontWeight: 500 }}>{lbl}</span>
                </div>
              ))}
            </div> */}
          </div>
        </div>

        {/* Form Panel */}
        <div style={{ flex: 1, background: "#ffffff", display: "flex", alignItems: "center", justifyContent: "center", padding: "48px 40px", overflowY: "auto" }}>
          <div style={{ width: "100%", maxWidth: 380, display: "flex", flexDirection: "column" }}>
            <h2 style={{ fontSize: 26, fontWeight: 800, color: "#09090b", letterSpacing: "-0.03em", margin: "0 0 8px" }}>{isLogin ? "Welcome back." : "Create account."}</h2>
            <p style={{ fontSize: 14, color: "#71717a", margin: "0 0 28px", lineHeight: 1.6 }}>{isLogin ? "Sign in to access your voice workspace." : "Set up your ACE workspace in seconds."}</p>

            {/* Pills */}
            <div style={{ display: "flex", gap: 5, marginBottom: 24, background: "#f4f4f5", padding: 4, borderRadius: 10 }}>
              {["Sign In", "Sign Up"].map((label, i) => {
                const active = (i === 0) === isLogin;
                return (
                  <button key={label} onClick={() => { setIsLogin(i === 0); setError(null); setSuccess(null); }}
                    style={{ flex: 1, padding: "9px 0", borderRadius: 7, border: "none", fontSize: 13, fontWeight: 600, cursor: "pointer", background: active ? "#fff" : "transparent", color: active ? "#09090b" : "#a1a1aa", boxShadow: active ? "0 1px 3px rgba(0,0,0,0.1)" : "none", fontFamily: "Inter, system-ui, sans-serif", transition: "all 0.2s" }}>
                    {label}
                  </button>
                );
              })}
            </div>

            {error && <div style={{ display: "flex", alignItems: "center", padding: "11px 14px", borderRadius: 8, fontSize: 13, marginBottom: 16, background: "#fef2f2", color: "#dc2626", border: "1px solid #fecaca" }}><span style={{ marginRight: 6 }}>⚠</span>{error}</div>}
            {success && <div style={{ display: "flex", alignItems: "center", padding: "11px 14px", borderRadius: 8, fontSize: 13, marginBottom: 16, background: "#f0fdf4", color: "#16a34a", border: "1px solid #bbf7d0" }}><CheckCircle2 size={14} style={{ marginRight: 6 }} />{success}</div>}

            {renderFormFields()}
            <p style={{ fontSize: 11, color: "#9ca3af", textAlign: "center", lineHeight: 1.7, margin: "20px 0 0" }}>By continuing you agree to our <span style={{ color: "#111111", textDecoration: "underline", cursor: "pointer" }}>Terms</span> &amp; <span style={{ color: "#111111", textDecoration: "underline", cursor: "pointer" }}>Privacy Policy</span>.</p>
          </div>
        </div>
      </div>
    </>
  );
}

// ─── Shared field styles ───
const fs: Record<string, React.CSSProperties> = {
  group: { display: "flex", flexDirection: "column", gap: 6 },
  label: { fontSize: 12, fontWeight: 500 },
  wrap: { position: "relative", display: "flex", alignItems: "center" },
  icon: { position: "absolute", left: 13, pointerEvents: "none", transition: "color 0.2s" },
  input: {
    width: "100%", borderRadius: 10, padding: "12px 14px 12px 40px",
    fontSize: 14, outline: "none", transition: "border-color 0.2s, box-shadow 0.2s",
    fontFamily: "Inter, system-ui, sans-serif", boxSizing: "border-box",
    border: "1.5px solid #e5e7eb",
  },
  lightInput: { background: "#fafafa", color: "#111827" },
  darkInput: { background: "#141414", color: "#e5e5e5", fontSize: 16 },
  submitBtn: {
    width: "100%", background: "#111111", color: "#fff", border: "none",
    borderRadius: 10, padding: "14px 20px", fontSize: 14, fontWeight: 600,
    cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
    gap: 8, transition: "background 0.2s", fontFamily: "Inter, system-ui, sans-serif",
    letterSpacing: "-0.01em",
  },
};
