"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { User, Lock, CheckCircle2, Loader2, Shield, Eye, EyeOff, LogOut } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { useAuthStore } from "@/store/authStore";
import { supabase } from "@/lib/supabase";

const card = { background: "var(--card)", border: "1px solid var(--border)", borderRadius: "1rem", overflow: "hidden", boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)" };
const hdr = { padding: "1.25rem 1.5rem", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: "0.75rem", background: "rgba(255,255,255,0.02)" };
const body = { padding: "1.5rem", display: "flex", flexDirection: "column" as const, gap: "1.5rem" };
const lbl = { fontSize: "0.8125rem", fontWeight: 600, color: "var(--foreground)", marginBottom: "0.375rem" } as React.CSSProperties;
const inp = { width: "100%", background: "var(--input)", border: "1px solid var(--border)", borderRadius: "0.5rem", padding: "0.625rem 0.875rem", fontSize: "0.875rem", color: "var(--foreground)", fontFamily: "var(--font-mono)", outline: "none", transition: "border-color 0.2s" } as React.CSSProperties;
const btnA = { padding: "0.625rem 1.25rem", borderRadius: "0.5rem", fontSize: "0.875rem", fontWeight: 600, cursor: "pointer", border: "1px solid var(--ring)", background: "var(--primary)", color: "var(--primary-foreground)", transition: "all 0.15s", boxShadow: "0 2px 4px rgba(0,0,0,0.1)", display: "flex", alignItems: "center", justifyContent: "center", gap: "0.5rem" } as React.CSSProperties;

export default function ProfilePage() {
  const { user, signOut } = useAuthStore();
  
  // Profile State
  const [displayName, setDisplayName] = useState("");
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileSuccess, setProfileSuccess] = useState(false);
  const [profileError, setProfileError] = useState("");

  // Password State
  const [newPassword, setNewPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [passwordSuccess, setPasswordSuccess] = useState(false);
  const [passwordError, setPasswordError] = useState("");

  useEffect(() => {
    if (user?.user_metadata?.display_name) {
      setDisplayName(user.user_metadata.display_name);
    }
  }, [user]);

  const handleUpdateProfile = async () => {
    if (!displayName.trim()) return;
    setProfileSaving(true);
    setProfileError("");
    setProfileSuccess(false);

    try {
      const { error } = await supabase.auth.updateUser({
        data: { display_name: displayName.trim() }
      });

      if (error) throw error;
      
      setProfileSuccess(true);
      setTimeout(() => setProfileSuccess(false), 3000);
      
      // Update local state to reflect immediately
      useAuthStore.setState((state) => ({
        user: state.user ? { ...state.user, user_metadata: { ...state.user.user_metadata, display_name: displayName.trim() } } : null
      }));

    } catch (err: any) {
      setProfileError(err.message || "Failed to update profile.");
    } finally {
      setProfileSaving(false);
    }
  };

  const handleUpdatePassword = async () => {
    if (!newPassword || newPassword.length < 6) {
      setPasswordError("Password must be at least 6 characters.");
      return;
    }
    setPasswordSaving(true);
    setPasswordError("");
    setPasswordSuccess(false);

    try {
      const { error } = await supabase.auth.updateUser({
        password: newPassword
      });

      if (error) throw error;
      
      setPasswordSuccess(true);
      setNewPassword("");
      setTimeout(() => setPasswordSuccess(false), 3000);
    } catch (err: any) {
      setPasswordError(err.message || "Failed to update password.");
    } finally {
      setPasswordSaving(false);
    }
  };

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "var(--background)" }}>
      <Sidebar />
      <div style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}>
        <TopBar />
        <main style={{ flex: 1, overflowY: "auto", padding: "2.5rem" }}>
          <div style={{ width: "100%", maxWidth: "800px", margin: "0 auto", display: "flex", flexDirection: "column", gap: "2rem" }}>
            
            <div>
              <h1 style={{ fontSize: "1.75rem", fontWeight: 600, color: "var(--foreground)", letterSpacing: "-0.02em", display: "flex", alignItems: "center", gap: "0.625rem" }}>
                <User style={{ width: "1.75rem", height: "1.75rem", color: "var(--primary)" }} /> My Profile
              </h1>
              <p style={{ color: "var(--muted-foreground)", marginTop: "0.375rem", fontSize: "0.9375rem" }}>
                Manage your personal information and security settings.
              </p>
            </div>

            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
              
              {/* Profile Information Card */}
              <section style={card}>
                <div style={hdr}>
                  <Shield style={{ width: "1.25rem", height: "1.25rem", color: "var(--muted-foreground)" }} />
                  <span style={{ fontSize: "1rem", fontWeight: 600, color: "var(--foreground)" }}>Personal Information</span>
                </div>
                <div style={body}>
                  <div>
                    <p style={lbl}>Email Address</p>
                    <input style={{ ...inp, opacity: 0.6, cursor: "not-allowed" }} value={user?.email || ""} disabled />
                    <p style={{ fontSize: "0.75rem", color: "var(--muted-foreground)", marginTop: "0.375rem" }}>Your email address cannot be changed.</p>
                  </div>

                  <div>
                    <p style={lbl}>Display Name</p>
                    <input 
                      style={inp} 
                      value={displayName} 
                      onChange={(e) => setDisplayName(e.target.value)} 
                      placeholder="e.g. John Smith"
                      onFocus={(e) => { (e.target as HTMLInputElement).style.borderColor = "var(--ring)"; }}
                      onBlur={(e)  => { (e.target as HTMLInputElement).style.borderColor  = "var(--border)"; }}
                    />
                  </div>

                  {profileError && (
                    <div style={{ padding: "0.75rem", borderRadius: "0.5rem", fontSize: "0.8125rem", fontWeight: 500, background: "rgba(239,68,68,0.1)", color: "#dc2626", border: "1px solid #ef444430" }}>
                      {profileError}
                    </div>
                  )}

                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingTop: "0.5rem", borderTop: "1px solid var(--border)" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--primary)", fontSize: "0.875rem", fontWeight: 500, opacity: profileSuccess ? 1 : 0, transition: "opacity 0.2s" }}>
                      <CheckCircle2 size={16} /> Profile updated successfully
                    </div>
                    <button 
                      onClick={handleUpdateProfile} 
                      disabled={profileSaving || displayName === user?.user_metadata?.display_name}
                      style={{ ...btnA, opacity: (profileSaving || displayName === user?.user_metadata?.display_name) ? 0.6 : 1 }}
                    >
                      {profileSaving ? <Loader2 size={16} className="animate-spin" /> : null}
                      Save Changes
                    </button>
                  </div>
                </div>
              </section>

              {/* Password Card */}
              <section style={{ ...card, marginTop: "2rem" }}>
                <div style={hdr}>
                  <Lock style={{ width: "1.25rem", height: "1.25rem", color: "var(--muted-foreground)" }} />
                  <span style={{ fontSize: "1rem", fontWeight: 600, color: "var(--foreground)" }}>Security</span>
                </div>
                <div style={body}>
                  <div>
                    <p style={lbl}>New Password</p>
                    <div style={{ position: "relative" }}>
                      <input 
                        type={showPassword ? "text" : "password"} 
                        style={{ ...inp, paddingRight: "3rem" }} 
                        placeholder="••••••••" 
                        value={newPassword} 
                        onChange={(e) => setNewPassword(e.target.value)} 
                        onFocus={(e) => { (e.target as HTMLInputElement).style.borderColor = "var(--ring)"; }}
                        onBlur={(e)  => { (e.target as HTMLInputElement).style.borderColor  = "var(--border)"; }}
                      />
                      <button onClick={() => setShowPassword(!showPassword)}
                        style={{ position: "absolute", right: "1rem", top: "50%", transform: "translateY(-50%)", background: "none", border: "none", cursor: "pointer", color: "var(--muted-foreground)", display: "flex" }}>
                        {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                    </div>
                    <p style={{ fontSize: "0.75rem", color: "var(--muted-foreground)", marginTop: "0.375rem" }}>Must be at least 6 characters long.</p>
                  </div>

                  {passwordError && (
                    <div style={{ padding: "0.75rem", borderRadius: "0.5rem", fontSize: "0.8125rem", fontWeight: 500, background: "rgba(239,68,68,0.1)", color: "#dc2626", border: "1px solid #ef444430" }}>
                      {passwordError}
                    </div>
                  )}

                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingTop: "0.5rem", borderTop: "1px solid var(--border)" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--primary)", fontSize: "0.875rem", fontWeight: 500, opacity: passwordSuccess ? 1 : 0, transition: "opacity 0.2s" }}>
                      <CheckCircle2 size={16} /> Password updated securely
                    </div>
                    <button 
                      onClick={handleUpdatePassword} 
                      disabled={passwordSaving || !newPassword}
                      style={{ ...btnA, opacity: (passwordSaving || !newPassword) ? 0.6 : 1 }}
                    >
                      {passwordSaving ? <Loader2 size={16} className="animate-spin" /> : null}
                      Update Password
                    </button>
                  </div>
                </div>
              </section>

              {/* Danger Zone */}
              <section style={{ ...card, marginTop: "2rem", border: "1px solid rgba(239, 68, 68, 0.2)" }}>
                <div style={{ ...hdr, borderBottom: "1px solid rgba(239, 68, 68, 0.1)" }}>
                  <LogOut style={{ width: "1.25rem", height: "1.25rem", color: "#ef4444" }} />
                  <span style={{ fontSize: "1rem", fontWeight: 600, color: "var(--foreground)" }}>Account Actions</span>
                </div>
                <div style={{ ...body, flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
                  <div>
                    <p style={{ ...lbl, color: "var(--foreground)" }}>Log Out</p>
                    <p style={{ fontSize: "0.875rem", color: "var(--muted-foreground)", marginTop: "0.25rem" }}>
                      Securely log out of your ACE account on this device.
                    </p>
                  </div>
                  <button 
                    onClick={() => signOut()} 
                    style={{ ...btnA, background: "rgba(239, 68, 68, 0.1)", color: "#ef4444", border: "1px solid rgba(239, 68, 68, 0.2)" }}
                    onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "rgba(239, 68, 68, 0.2)"; }}
                    onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "rgba(239, 68, 68, 0.1)"; }}
                  >
                    <LogOut size={16} />
                    Log Out
                  </button>
                </div>
              </section>

            </motion.div>
          </div>
        </main>
      </div>
    </div>
  );
}
