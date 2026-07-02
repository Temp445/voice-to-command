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
    <div className="flex h-screen overflow-hidden bg-[var(--background)]">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 md:p-10">
          <div className="max-w-7xl mx-auto w-full flex flex-col gap-8">

            {/* Login required banner */}
            {notAuthenticated && (
              <motion.div
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex flex-col sm:flex-row items-start sm:items-center gap-3 p-4 rounded-xl border border-amber-500/35 bg-amber-500/8"
              >
                <LogIn className="w-4 h-4 text-amber-500 shrink-0" />
                <span className="text-sm text-amber-500 flex-1">
                  You are not logged in. Voice commands and automations will not work until you sign in.
                </span>
                <a
                  href="/auth/login"
                  className="px-3.5 py-1.5 rounded-lg bg-amber-500/15 border border-amber-500/40 text-amber-500 text-[13px] font-semibold no-underline hover:bg-amber-500/25 transition-colors cursor-pointer whitespace-nowrap self-start sm:self-auto"
                >
                  Log In
                </a>
              </motion.div>
            )}

            {/* Header */}
            <div>
              <h1 className="text-2xl sm:text-3xl font-semibold text-[var(--foreground)] tracking-tight">
                Dashboard
              </h1>
              <p className="text-zinc-400 mt-1.5 text-sm sm:text-base">
                Your AI-powered desktop assistant — always listening, always ready.
              </p>
            </div>

            {/* Status bar */}
            <StatusBar />

            {/* 2-column grid */}
            <div className="grid grid-cols-1 lg:grid-cols-[1fr_2fr] gap-6">
              <VoicePanel />
              <div className="flex flex-col gap-5">
                <QuickActions />
                {(partialTranscript || transcript) && (
                  <div className="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-4 shadow-sm">
                    <p className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider mb-2">
                      {partialTranscript ? "Live Transcript" : "Last Transcript"}
                    </p>
                    <p className="text-[var(--foreground)] font-mono text-sm leading-relaxed">
                      {partialTranscript || transcript}
                      {partialTranscript && <span className="animate-pulse">...</span>}
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
