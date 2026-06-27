"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { User, Lock, CheckCircle2, Loader2, Shield, Eye, EyeOff, LogOut } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { useAuthStore } from "@/store/authStore";
import { supabase } from "@/lib/supabase";

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
    <div className="flex h-screen overflow-hidden bg-[var(--background)]">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-y-auto p-10">
          <div className="w-full max-w-[800px] mx-auto flex flex-col gap-8">
            
            <div>
              <h1 className="text-3xl font-semibold text-[var(--foreground)] tracking-tight flex items-center gap-2.5">
                <User className="w-7 h-7 text-[var(--primary)]" /> My Profile
              </h1>
              <p className="text-zinc-500 mt-1.5 text-[15px]">
                Manage your personal information and security settings.
              </p>
            </div>

            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
              
              {/* Profile Information Card */}
              <section className="bg-[var(--card)] border border-[var(--border)] rounded-2xl overflow-hidden shadow-md">
                <div className="px-6 py-5 border-b border-[var(--border)] flex items-center gap-3 bg-white/[0.02]">
                  <Shield className="w-5 h-5 text-zinc-500" />
                  <span className="text-base font-semibold text-[var(--foreground)]">Personal Information</span>
                </div>
                <div className="p-6 flex flex-col gap-6">
                  <div>
                    <p className="text-[13px] font-semibold text-[var(--foreground)] mb-1.5">Email Address</p>
                    <input 
                      className="w-full bg-[var(--input)] border border-[var(--border)] rounded-lg px-3.5 py-2.5 text-sm text-[var(--foreground)] font-mono outline-none opacity-60 cursor-not-allowed" 
                      value={user?.email || ""} 
                      disabled 
                    />
                    <p className="text-xs text-zinc-500 mt-1.5">Your email address cannot be changed.</p>
                  </div>

                  <div>
                    <p className="text-[13px] font-semibold text-[var(--foreground)] mb-1.5">Display Name</p>
                    <input 
                      className="w-full bg-[var(--input)] border border-[var(--border)] rounded-lg px-3.5 py-2.5 text-sm text-[var(--foreground)] font-mono outline-none transition-colors duration-200 focus:border-[var(--ring)]" 
                      value={displayName} 
                      onChange={(e) => setDisplayName(e.target.value)} 
                      placeholder="e.g. John Smith"
                    />
                  </div>

                  {profileError && (
                    <div className="p-3 rounded-lg text-[13px] font-medium bg-red-500/10 text-red-600 border border-red-500/20">
                      {profileError}
                    </div>
                  )}

                  <div className="flex items-center justify-between pt-2 border-t border-[var(--border)]">
                    <div className={`flex items-center gap-2 text-[var(--primary)] text-sm font-medium transition-opacity duration-200 ${profileSuccess ? "opacity-100" : "opacity-0"}`}>
                      <CheckCircle2 size={16} /> Profile updated successfully
                    </div>
                    <button 
                      onClick={handleUpdateProfile} 
                      disabled={profileSaving || displayName === user?.user_metadata?.display_name}
                      className={`px-5 py-2.5 rounded-lg text-sm font-semibold border border-[var(--ring)] bg-[var(--primary)] text-[var(--primary-foreground)] transition-all duration-150 shadow-sm flex items-center justify-center gap-2 ${profileSaving || displayName === user?.user_metadata?.display_name ? "opacity-60 cursor-not-allowed" : "opacity-100 hover:opacity-90 active:scale-[0.98]"}`}
                    >
                      {profileSaving ? <Loader2 size={16} className="animate-spin" /> : null}
                      Save Changes
                    </button>
                  </div>
                </div>
              </section>

              {/* Password Card */}
              <section className="bg-[var(--card)] border border-[var(--border)] rounded-2xl overflow-hidden shadow-md mt-8">
                <div className="px-6 py-5 border-b border-[var(--border)] flex items-center gap-3 bg-white/[0.02]">
                  <Lock className="w-5 h-5 text-zinc-500" />
                  <span className="text-base font-semibold text-[var(--foreground)]">Security</span>
                </div>
                <div className="p-6 flex flex-col gap-6">
                  <div>
                    <p className="text-[13px] font-semibold text-[var(--foreground)] mb-1.5">New Password</p>
                    <div className="relative">
                      <input 
                        type={showPassword ? "text" : "password"} 
                        className="w-full bg-[var(--input)] border border-[var(--border)] rounded-lg pl-3.5 pr-12 py-2.5 text-sm text-[var(--foreground)] font-mono outline-none transition-colors duration-200 focus:border-[var(--ring)]" 
                        placeholder="••••••••" 
                        value={newPassword} 
                        onChange={(e) => setNewPassword(e.target.value)} 
                      />
                      <button 
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-4 top-1/2 -translate-y-1/2 bg-transparent border-none cursor-pointer text-zinc-500 flex"
                      >
                        {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                    </div>
                    <p className="text-xs text-zinc-500 mt-1.5">Must be at least 6 characters long.</p>
                  </div>

                  {passwordError && (
                    <div className="p-3 rounded-lg text-[13px] font-medium bg-red-500/10 text-red-600 border border-red-500/20">
                      {passwordError}
                    </div>
                  )}

                  <div className="flex items-center justify-between pt-2 border-t border-[var(--border)]">
                    <div className={`flex items-center gap-2 text-[var(--primary)] text-sm font-medium transition-opacity duration-200 ${passwordSuccess ? "opacity-100" : "opacity-0"}`}>
                      <CheckCircle2 size={16} /> Password updated securely
                    </div>
                    <button 
                      onClick={handleUpdatePassword} 
                      disabled={passwordSaving || !newPassword}
                      className={`px-5 py-2.5 rounded-lg text-sm font-semibold border border-[var(--ring)] bg-[var(--primary)] text-[var(--primary-foreground)] transition-all duration-150 shadow-sm flex items-center justify-center gap-2 ${passwordSaving || !newPassword ? "opacity-60 cursor-not-allowed" : "opacity-100 hover:opacity-90 active:scale-[0.98]"}`}
                    >
                      {passwordSaving ? <Loader2 size={16} className="animate-spin" /> : null}
                      Update Password
                    </button>
                  </div>
                </div>
              </section>

              {/* Danger Zone */}
              <section className="bg-[var(--card)] border border-red-500/20 rounded-2xl overflow-hidden shadow-md mt-8">
                <div className="px-6 py-5 border-b border-red-500/10 flex items-center gap-3 bg-white/[0.02]">
                  <LogOut className="w-5 h-5 text-red-500" />
                  <span className="text-base font-semibold text-[var(--foreground)]">Account Actions</span>
                </div>
                <div className="p-6 flex flex-row items-center justify-between gap-6">
                  <div>
                    <p className="text-[13px] font-semibold text-[var(--foreground)] mb-1.5">Log Out</p>
                    <p className="text-sm text-zinc-500 mt-1">
                      Securely log out of your ACE account on this device.
                    </p>
                  </div>
                  <button 
                    onClick={() => signOut()} 
                    className="px-5 py-2.5 rounded-lg text-sm font-semibold border border-red-500/20 bg-red-500/10 text-red-500 transition-all duration-150 shadow-sm flex items-center justify-center gap-2 hover:bg-red-500/20 active:scale-[0.98]"
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
