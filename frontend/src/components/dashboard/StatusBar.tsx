"use client";

import { Mic, Cpu, Zap, Bot } from "lucide-react";
import { useVoiceStore } from "@/store/voiceStore";
import { useCommandStore } from "@/store/commandStore";
import { useSettingsStore } from "@/store/settingsStore";

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

  const values: Record<string, string> = {
    voice:    pipelineState,
    commands: `${history.length} total`,
    engine:   `Whisper ${settings.whisperModel || 'Base'}`,
    llm:      settings.llmEnabled ? `${settings.llmProvider.toUpperCase()}` : "Disabled",
    uptime:   "Active",
  };

  return (
    <div className="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-4 sm:p-6 flex flex-col gap-4 sm:gap-5 shadow-sm">
      <div className="flex justify-between items-center">
        <h3 className="text-[13px] font-bold text-[var(--foreground)] uppercase tracking-wider opacity-90">
          System Status
        </h3>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {STATS.map(({ key, icon: Icon, label, color }) => (
          <div 
            key={key} 
            className="bg-[var(--secondary)] border border-[var(--border)] rounded-xl p-4 flex items-center gap-3.5 shadow-xs"
          >
            <div className="w-10 h-10 rounded-lg bg-[var(--background)] border border-[var(--border)]/40 flex items-center justify-center shrink-0">
              <Icon size={18} style={{ color }} className="shrink-0" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-0.5">
                {label}
              </p>
              <p 
                style={{ color }} 
                className="text-[14px] font-bold capitalize truncate"
              >
                {values[key]}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}