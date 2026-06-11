"use client";

import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { VoicePanel } from "@/components/voice/VoicePanel";
import { ActivityFeed } from "@/components/dashboard/ActivityFeed";
import { QuickActions } from "@/components/dashboard/QuickActions";
import { StatusBar } from "@/components/dashboard/StatusBar";
import { useVoiceStore } from "@/store/voiceStore";

export default function DashboardPage() {
  const { transcript } = useVoiceStore();

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "var(--background)" }}>
      <Sidebar />
      <div style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}>
        <TopBar />
        <main style={{ flex: 1, overflowY: "auto", padding: "2.5rem 3.5rem" }}>
          <div style={{ maxWidth: "1280px", margin: "0 auto", display: "flex", flexDirection: "column", gap: "2rem" }}>

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
                {transcript && (
                  <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: "1rem", padding: "1rem" }}>
                    <p style={{ fontSize: "0.6875rem", fontWeight: 600, color: "var(--muted-foreground)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "0.5rem" }}>
                      Last Transcript
                    </p>
                    <p style={{ color: "var(--foreground)", fontFamily: "var(--font-mono)", fontSize: "0.875rem" }}>{transcript}</p>
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
