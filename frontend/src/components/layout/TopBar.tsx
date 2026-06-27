"use client";

import Link from "next/link";
import { User, Wifi, WifiOff, Activity } from "lucide-react";
import { useVoiceStore } from "@/store/voiceStore";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const STATE_BADGE: Record<string, string> = {
  idle:       "bg-zinc-500/10 text-zinc-400 border-zinc-500/20",
  listening:  "bg-green-500/10 text-green-500 border-green-500/20",
  processing: "bg-amber-500/10 text-amber-500 border-amber-500/20",
  speaking:   "bg-blue-500/10 text-blue-500 border-blue-500/20",
  error:      "bg-red-500/10 text-red-500 border-red-500/20",
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
    <header 
      data-tauri-drag-region 
      className="h-16 flex items-center px-6 gap-4 border-b border-[var(--border)] bg-[var(--background)] shrink-0 select-none"
    >
      {/* Active Tab Badge on the left */}
      <div className="flex-1 flex items-center">
        {tabName && connected && (
          <div 
            title={`Active Browser Tab: ${activeTabUrl}`}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-blue-500/8 border border-blue-500/15 text-blue-400 text-xs font-medium font-mono"
          >
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-blue-500" />
            <span>Target:</span>
            <span className="text-[var(--foreground)] font-semibold">{tabName}</span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-3 ml-auto">
        {/* API Ping Status */}
        {ping && (
          <div title="Server Ping" className="flex items-center gap-1 text-xs text-zinc-400 mr-2 cursor-help">
            <Activity className="w-3.5 h-3.5" />
            <span>{ping}</span>
          </div>
        )}

        {/* WS status */}
        <div className="flex items-center gap-1.5 text-xs">
          {connected
            ? <Wifi className="w-3.5 h-3.5 text-green-500" />
            : <WifiOff className="w-3.5 h-3.5 text-red-500" />
          }
          <span className={connected ? "text-green-500" : "text-red-500"}>{connected ? "Connected" : "Offline"}</span>
        </div>

        {/* Pipeline badge */}
        <div className={`px-3 py-1 rounded-full text-[11px] font-semibold capitalize border ${badge}`}>
          {pipelineState}
        </div>

        {/* Avatar */}
        <Link 
          href="/profile" 
          className="w-8 h-8 rounded-full bg-[var(--foreground)] text-[var(--background)] flex items-center justify-center border-none cursor-pointer no-underline hover:opacity-90 transition-all"
        >
          <User className="w-3.5 h-3.5" />
        </Link>
      </div>
    </header>
  );
}
