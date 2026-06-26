"use client";

import Link from "next/link";
import { User, Wifi, WifiOff, Activity } from "lucide-react";
import { useVoiceStore } from "@/store/voiceStore";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const STATE_BADGE: Record<string, { bg: string; color: string; border: string }> = {
  idle:       { bg: "rgba(107,114,128,0.12)", color: "#9CA3AF", border: "rgba(107,114,128,0.2)" },
  listening:  { bg: "rgba(34,197,94,0.12)",   color: "#22c55e", border: "rgba(34,197,94,0.25)" },
  processing: { bg: "rgba(245,158,11,0.12)",  color: "#f59e0b", border: "rgba(245,158,11,0.25)" },
  speaking:   { bg: "rgba(59,130,246,0.12)",  color: "#3b82f6", border: "rgba(59,130,246,0.25)" },
  error:      { bg: "rgba(239,68,68,0.12)",   color: "#ef4444", border: "rgba(239,68,68,0.25)" },
};

export function TopBar() {
  const { pipelineState } = useVoiceStore();
  const { connected, activeTabTitle, activeTabUrl } = useWebSocket();
  const badge = STATE_BADGE[pipelineState] || STATE_BADGE.idle;
  
  const [ping, setPing] = useState<string | null>(null);

  // Helper to format the active tab display name
  const getTabDisplayName = () => {
    if (!activeTabUrl) return null;
    
    // Fallback/friendly title helper
    let cleanTitle = activeTabTitle || "";
    
    // Check if the title is empty or is a coroutine/promise string representation
    if (!cleanTitle || cleanTitle.includes("<coroutine") || cleanTitle.includes("[object Promise]")) {
      try {
        const urlObj = new URL(activeTabUrl);
        let hostname = urlObj.hostname;
        if (hostname.startsWith("www.")) {
          hostname = hostname.substring(4);
        }
        // Capitalize first letter of domain
        cleanTitle = hostname.charAt(0).toUpperCase() + hostname.slice(1);
      } catch (e) {
        cleanTitle = "Active Tab";
      }
    }
    
    // Truncate if too long
    if (cleanTitle.length > 25) {
      cleanTitle = cleanTitle.substring(0, 22) + "...";
    }
    
    return cleanTitle;
  };

  const tabName = getTabDisplayName();

  useEffect(() => {
    if (!connected) {
      setPing(null);
      return;
    }
    
    const measurePing = async () => {
      try {
        const res = await api.getHealthPing();
        if (res.processTime) {
          setPing(res.processTime);
        } else {
          setPing(`${res.networkTime}ms`);
        }
      } catch (e) {
        setPing(null);
      }
    };

    measurePing();
    const interval = setInterval(measurePing, 10000);
    return () => clearInterval(interval);
  }, [connected]);

  return (
    <header data-tauri-drag-region style={{
      height: "4rem", display: "flex", alignItems: "center", padding: "0 1.5rem", gap: "1rem",
      borderBottom: "1px solid var(--border)", background: "var(--background)", flexShrink: 0,
      userSelect: "none"
    }}>
      {/* Active Tab Badge on the left */}
      <div style={{ flex: 1, display: "flex", alignItems: "center" }}>
        {tabName && connected && (
          <div 
            title={`Active Browser Tab: ${activeTabUrl}`}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              padding: "0.35rem 0.75rem",
              borderRadius: "0.5rem",
              background: "rgba(59, 130, 246, 0.08)",
              border: "1px solid rgba(59, 130, 246, 0.15)",
              color: "#60a5fa",
              fontSize: "0.75rem",
              fontWeight: 500,
              fontFamily: "var(--font-mono)",
            }}
          >
            <span style={{ display: "inline-block", width: "0.375rem", height: "0.375rem", borderRadius: "50%", background: "#3b82f6" }} />
            <span>Target:</span>
            <span style={{ color: "var(--foreground)", fontWeight: 600 }}>{tabName}</span>
          </div>
        )}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginLeft: "auto" }}>
        {/* API Ping Status */}
        {ping && (
          <div title="Server Ping" style={{ display: "flex", alignItems: "center", gap: "0.25rem", fontSize: "0.75rem", color: "#9CA3AF", marginRight: "0.5rem", cursor: "help" }}>
            <Activity style={{ width: "0.875rem", height: "0.875rem" }} />
            <span>{ping}</span>
          </div>
        )}

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
