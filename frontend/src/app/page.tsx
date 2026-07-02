"use client";

import { motion } from "framer-motion";
import { LogIn } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { VoicePanel } from "@/components/voice/VoicePanel";
import { ActivityFeed } from "@/components/dashboard/ActivityFeed";
import { QuickActions } from "@/components/dashboard/QuickActions";
import { StatusBar } from "@/components/dashboard/StatusBar";
import { useVoiceStore } from "@/store/voiceStore";
import { useWSStore } from "@/hooks/useWebSocket";

export default function DashboardPage() {
  const { transcript, partialTranscript } = useVoiceStore();
  const { notAuthenticated } = useWSStore();

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "var(--background)" }}>
      <Sidebar />
      <div style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}>
        <TopBar />
        <main style={{ flex: 1, overflowY: "auto", padding: "2.5rem 3.5rem" }}>
          <div style={{ maxWidth: "1280px", margin: "0 auto", display: "flex", flexDirection: "column", gap: "2rem" }}>

            {/* Login required banner */}
            {notAuthenticated && (
              <motion.div
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.75rem",
                  padding: "0.75rem 1.125rem",
                  borderRadius: "0.75rem",
                  border: "1px solid rgba(245,158,11,0.35)",
                  background: "rgba(245,158,11,0.08)",
                }}
              >
                <LogIn style={{ width: "1rem", height: "1rem", color: "#f59e0b", flexShrink: 0 }} />
                <span style={{ fontSize: "0.875rem", color: "#f59e0b", flex: 1 }}>
                  You are not logged in. Voice commands and automations will not work until you sign in.
                </span>
                <a
                  href="/auth/login"
                  style={{
                    padding: "0.3rem 0.875rem",
                    borderRadius: "0.5rem",
                    background: "rgba(245,158,11,0.15)",
                    border: "1px solid rgba(245,158,11,0.4)",
                    color: "#f59e0b",
                    fontSize: "0.8125rem",
                    fontWeight: 600,
                    textDecoration: "none",
                    whiteSpace: "nowrap",
                    cursor: "pointer",
                  }}
                >
                  Log In
                </a>
              </motion.div>
            )}

            {/* Header */}
            <div>
              <h1 style={{ fontSize: "1.75rem", fontWeight: 600, color: "var(--foreground)", letterSpacing: "-0.02em" }}>
               Dashboard
              </h1>
              <p style={{ color: "var(--muted-foreground)", marginTop: "0.375rem", fontSize: "0.9375rem" }}>
                Your AI-powered desktop assistant — always listening, always ready.
              </p>
            </div>

            {/* Status bar */}
            <StatusBar />

            {/* 2-column grid */}
    <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: "1.5rem" }}>
              <VoicePanel />
              <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                <QuickActions />
                {(partialTranscript || transcript) && (
                  <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: "1rem", padding: "1rem" }}>
                    <p style={{ fontSize: "0.6875rem", fontWeight: 600, color: "var(--muted-foreground)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "0.5rem" }}>
                      {partialTranscript ? "Live Transcript" : "Last Transcript"}
                    </p>
                    <p style={{ color: "var(--foreground)", fontFamily: "var(--font-mono)", fontSize: "0.875rem" }}>
                      {partialTranscript || transcript}
                      {partialTranscript && <span style={{ animation: "pulse 1.5s infinite" }}>...</span>}
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Activity feed */}
            <ActivityFeed />
          </div>
        </main>
      </div>
    </div>
  );
}
