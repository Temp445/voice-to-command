"use client";

import { Bell, Search, User, Wifi, WifiOff } from "lucide-react";
import { useVoiceStore } from "@/store/voiceStore";
import { useWebSocket } from "@/hooks/useWebSocket";

const STATE_BADGE: Record<string, { bg: string; color: string; border: string }> = {
  idle:       { bg: "rgba(107,114,128,0.12)", color: "#9CA3AF", border: "rgba(107,114,128,0.2)" },
  listening:  { bg: "rgba(34,197,94,0.12)",   color: "#22c55e", border: "rgba(34,197,94,0.25)" },
  processing: { bg: "rgba(245,158,11,0.12)",  color: "#f59e0b", border: "rgba(245,158,11,0.25)" },
  speaking:   { bg: "rgba(59,130,246,0.12)",  color: "#3b82f6", border: "rgba(59,130,246,0.25)" },
  error:      { bg: "rgba(239,68,68,0.12)",   color: "#ef4444", border: "rgba(239,68,68,0.25)" },
};

export function TopBar() {
  const { pipelineState } = useVoiceStore();
  const { connected } = useWebSocket();
  const badge = STATE_BADGE[pipelineState] || STATE_BADGE.idle;

  return (
    <header style={{
      height: "3.5rem", display: "flex", alignItems: "center", padding: "0 1.5rem", gap: "1rem",
      borderBottom: "1px solid var(--border)", background: "var(--background)", flexShrink: 0,
    }}>
      {/* Search */}
      <div style={{ flex: 1, maxWidth: "28rem", position: "relative" }}>
        <Search style={{ position: "absolute", left: "0.75rem", top: "50%", transform: "translateY(-50%)", width: "0.875rem", height: "0.875rem", color: "var(--muted-foreground)" }} />
        <input
          type="text"
          placeholder="Search commands..."
          style={{
            width: "100%", background: "var(--secondary)", border: "1px solid var(--border)", borderRadius: "0.5rem",
            padding: "0.4rem 1rem 0.4rem 2.25rem", fontSize: "0.8125rem", color: "var(--foreground)",
            outline: "none", transition: "border 0.15s",
          }}
          onFocus={(e) => { (e.target as HTMLInputElement).style.borderColor = "var(--ring)"; }}
          onBlur={(e) => { (e.target as HTMLInputElement).style.borderColor = "var(--border)"; }}
        />
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginLeft: "auto" }}>
        {/* WS status */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.375rem", fontSize: "0.75rem" }}>
          {connected
            ? <Wifi  style={{ width: "0.875rem", height: "0.875rem", color: "#22c55e" }} />
            : <WifiOff style={{ width: "0.875rem", height: "0.875rem", color: "#ef4444" }} />
          }
          <span style={{ color: connected ? "#22c55e" : "#ef4444" }}>{connected ? "Connected" : "Offline"}</span>
        </div>

        {/* Pipeline badge */}
        <div style={{
          padding: "0.2rem 0.75rem", borderRadius: "9999px", fontSize: "0.7rem", fontWeight: 600,
          textTransform: "capitalize", background: badge.bg, color: badge.color, border: `1px solid ${badge.border}`,
        }}>
          {pipelineState}
        </div>

        {/* Bell */}
        <button
          style={{ width: "2rem", height: "2rem", borderRadius: "0.375rem", display: "flex", alignItems: "center", justifyContent: "center", background: "transparent", border: "1px solid transparent", color: "var(--muted-foreground)", cursor: "pointer", position: "relative", transition: "all 0.15s" }}
          onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "var(--secondary)"; (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--border)"; (e.currentTarget as HTMLButtonElement).style.color = "var(--foreground)"; }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "transparent"; (e.currentTarget as HTMLButtonElement).style.borderColor = "transparent"; (e.currentTarget as HTMLButtonElement).style.color = "var(--muted-foreground)"; }}
        >
          <Bell style={{ width: "0.875rem", height: "0.875rem" }} />
          <span style={{ position: "absolute", top: "0.3rem", right: "0.3rem", width: "0.35rem", height: "0.35rem", background: "var(--foreground)", borderRadius: "9999px" }} />
        </button>

        {/* Avatar */}
        <button style={{
          width: "2rem", height: "2rem", borderRadius: "9999px", background: "var(--foreground)",
          color: "var(--background)", display: "flex", alignItems: "center", justifyContent: "center", border: "none", cursor: "pointer",
        }}>
          <User style={{ width: "0.875rem", height: "0.875rem" }} />
        </button>
      </div>
    </header>
  );
}
