"use client";

import { useState, useEffect } from "react";
import { Mic, Cpu, Zap, Clock, Bot } from "lucide-react";
import { useVoiceStore } from "@/store/voiceStore";
import { useCommandStore } from "@/store/commandStore";
import { useSettingsStore } from "@/store/settingsStore";

import { useRemoteMic } from "@/hooks/useRemoteMic";
import { useWSStore } from "@/hooks/useWebSocket";

const STATS = [
  { key: "voice",    icon: Mic,   label: "Voice",       color: "var(--foreground)" },
  { key: "commands", icon: Zap,   label: "Commands",    color: "var(--foreground)" },
  { key: "engine",   icon: Cpu,   label: "Engine",      color: "var(--foreground)" },
  { key: "llm",      icon: Bot,   label: "AI Model",    color: "var(--primary)"    },
];

export function StatusBar() {
  const { pipelineState } = useVoiceStore();
  const { history } = useCommandStore();
  const settings = useSettingsStore();
  const { isRecording, toggleRecording } = useRemoteMic();
  const { connected } = useWSStore();

  const values: Record<string, string> = {
    voice:    pipelineState,
    commands: `${history.length} total`,
    engine:   `Whisper ${settings.whisperModel || 'Base'}`,
    llm:      settings.llmEnabled ? `${settings.llmProvider.toUpperCase()}` : "Disabled",
    uptime:   "Active",
  };

  return (
    <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: "1rem", padding: "1.5rem", display: "flex", flexDirection: "column", gap: "1.25rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 style={{ fontSize: "0.8125rem", fontWeight: 600, color: "var(--foreground)", textTransform: "uppercase", letterSpacing: "0.06em" }}>System Status</h3>
        <button 
          onClick={toggleRecording}
          disabled={!connected}
          style={{
            padding: "0.4rem 0.8rem",
            fontSize: "0.8rem",
            borderRadius: "0.5rem",
            background: !connected ? "var(--secondary)" : isRecording ? "rgba(239,68,68,0.15)" : "rgba(34,197,94,0.15)",
            color: !connected ? "var(--muted-foreground)" : isRecording ? "#ef4444" : "#22c55e",
            border: `1px solid ${!connected ? "var(--border)" : isRecording ? "rgba(239,68,68,0.4)" : "rgba(34,197,94,0.4)"}`,
            cursor: !connected ? "not-allowed" : "pointer",
            display: "flex",
            alignItems: "center",
            gap: "0.4rem",
            transition: "all 0.2s",
            opacity: !connected ? 0.6 : 1
          }}
        >
          <Mic style={{ width: "0.9rem", height: "0.9rem" }} />
          {isRecording ? "Stop Remote Mic" : "Start Remote Mic"}
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "1rem" }}>
        {STATS.map(({ key, icon: Icon, label, color }) => (
          <div key={key} style={{ background: "var(--secondary)", border: "1px solid var(--border)", borderRadius: "0.75rem", padding: "1.25rem", display: "flex", alignItems: "center", gap: "1rem" }}>
            <div style={{ width: "2.5rem", height: "2.5rem", borderRadius: "0.5rem", background: "var(--background)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <Icon style={{ width: "1.25rem", height: "1.25rem", color }} />
            </div>
            <div style={{ minWidth: 0 }}>
              <p style={{ fontSize: "0.6875rem", color: "var(--muted-foreground)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "0.125rem" }}>{label}</p>
              <p style={{ fontSize: "0.9375rem", fontWeight: 600, color, textTransform: "capitalize", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {values[key]}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}