"use client";

import { useState, useEffect } from "react";
import { Mic, Cpu, Zap, Clock, Bot } from "lucide-react";
import { useVoiceStore } from "@/store/voiceStore";
import { useCommandStore } from "@/store/commandStore";
import { useSettingsStore } from "@/store/settingsStore";

import { useRemoteMic } from "@/hooks/useRemoteMic";

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

  const values: Record<string, string> = {
    voice:    pipelineState,
    commands: `${history.length} total`,
    engine:   `Whisper ${settings.whisperModel || 'Base'}`,
    llm:      settings.llmEnabled ? `${settings.llmProvider.toUpperCase()}` : "Disabled",
    uptime:   "Active",
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 style={{ fontSize: "0.9rem", fontWeight: 600, color: "var(--foreground)" }}>System Status</h3>
        <button 
          onClick={toggleRecording}
          style={{
            padding: "0.4rem 0.8rem",
            fontSize: "0.8rem",
            borderRadius: "0.5rem",
            background: isRecording ? "rgba(239,68,68,0.15)" : "rgba(34,197,94,0.15)",
            color: isRecording ? "#ef4444" : "#22c55e",
            border: `1px solid ${isRecording ? "rgba(239,68,68,0.4)" : "rgba(34,197,94,0.4)"}`,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: "0.4rem",
            transition: "all 0.2s"
          }}
        >
          <Mic style={{ width: "0.9rem", height: "0.9rem" }} />
          {isRecording ? "Stop Remote Mic" : "Start Remote Mic"}
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "0.75rem" }}>
        {STATS.map(({ key, icon: Icon, label, color }) => (
          <div key={key} className="stat-card">
            <div className="stat-card-icon">
              <Icon style={{ width: "1rem", height: "1rem", color }} />
            </div>
            <div style={{ minWidth: 0 }}>
              <p style={{ fontSize: "0.7rem", color: "var(--muted-foreground)", textTransform: "uppercase", letterSpacing: "0.06em" }}>{label}</p>
              <p style={{ fontSize: "0.875rem", fontWeight: 600, color, textTransform: "capitalize", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {values[key]}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
