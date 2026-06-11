"use client";

import Link from "next/link";
import { User, Wifi, WifiOff } from "lucide-react";
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
    <header data-tauri-drag-region style={{
      height: "4rem", display: "flex", alignItems: "center", padding: "0 1.5rem", gap: "1rem",
      borderBottom: "1px solid var(--border)", background: "var(--background)", flexShrink: 0,
      userSelect: "none"
    }}>
      {/* Empty flex spacer to push the right items to the edge */}
      <div style={{ flex: 1 }} />

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



        {/* Avatar */}
        <Link href="/profile" style={{
          width: "2rem", height: "2rem", borderRadius: "9999px", background: "var(--foreground)",
          color: "var(--background)", display: "flex", alignItems: "center", justifyContent: "center", border: "none", cursor: "pointer", textDecoration: "none"
        }}>
          <User style={{ width: "0.875rem", height: "0.875rem" }} />
        </Link>
      </div>
    </header>
  );
}
