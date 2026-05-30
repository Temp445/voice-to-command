"use client";

import { useState, useEffect } from "react";
import { Mic, Cpu, Zap, Clock, Bot } from "lucide-react";
import { useVoiceStore } from "@/store/voiceStore";
import { useCommandStore } from "@/store/commandStore";
import { useSettingsStore } from "@/store/settingsStore";

const STATS = [
  { key: "voice",    icon: Mic,   label: "Voice",       color: "var(--foreground)" },
  { key: "commands", icon: Zap,   label: "Commands",    color: "var(--foreground)" },
  { key: "engine",   icon: Cpu,   label: "Engine",      color: "var(--foreground)" },
  { key: "llm",      icon: Bot,   label: "AI Model",    color: "var(--primary)"    },
  { key: "uptime",   icon: Clock, label: "Uptime",      color: "#22c55e"           },
];

export function StatusBar() {
  const { pipelineState } = useVoiceStore();
  const { history } = useCommandStore();
  const settings = useSettingsStore();

  const values: Record<string, string> = {
    voice:    pipelineState,
    commands: `${history.length} total`,
    engine:   "Whisper Base",
    llm:      settings.llmEnabled ? `${settings.llmProvider.toUpperCase()} (${settings.llmMode})` : "Disabled",
    uptime:   "Active",
  };

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "0.75rem" }}>
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
  );
}
