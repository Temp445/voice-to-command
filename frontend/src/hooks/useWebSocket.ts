"use client";

import { useEffect, useRef, useCallback } from "react";
import { useVoiceStore } from "@/store/voiceStore";
import { useCommandStore } from "@/store/commandStore";
import { create } from "zustand";

interface WSStore { connected: boolean; setConnected: (v: boolean) => void; }
export const useWSStore = create<WSStore>((set) => ({
  connected: false,
  setConnected: (v) => set({ connected: v }),
}));

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const { setPipelineState, setTranscript, setWakeWordActive } = useVoiceStore();
  const { addEntry, updateEntry } = useCommandStore();
  const { connected, setConnected } = useWSStore();

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    let wsUrl = "ws://localhost:8000/ws";
    
    if (process.env.NEXT_PUBLIC_API_URL) {
      const baseUrl = process.env.NEXT_PUBLIC_API_URL.replace(/\/api$/, "");
      wsUrl = baseUrl.replace(/^http/, "ws") + "/ws";
    } else if (typeof window !== "undefined" && window.location.hostname.includes("devtunnels.ms")) {
      const isHttps = window.location.protocol === "https:";
      const host = window.location.host.replace("-3000", "-8000");
      wsUrl = `${isHttps ? "wss" : "ws"}://${host}/ws`;
    }

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      console.log("✅ WebSocket connected");
    };

    ws.onmessage = (e) => {
      try {
        const { event, data } = JSON.parse(e.data);
        switch (event) {
          case "pipeline_state":
            setPipelineState(data.state);
            if (data.wake_word_active !== undefined) {
              setWakeWordActive(data.wake_word_active);
            }
            break;
          case "transcript":
            setTranscript(data.text, data.is_final);
            break;
          case "command_executed":
            addEntry({ ...data, source: "voice" });
            break;
          case "wake_word_detected":
            setWakeWordActive(true);
            setTimeout(() => setWakeWordActive(false), 2000);
            break;
          case "settings_updated":
            // Handled by settings store
            break;
        }
      } catch {}
    };

    ws.onclose = () => {
      setConnected(false);
      // Auto-reconnect after 3s
      setTimeout(connect, 3000);
    };

    ws.onerror = () => ws.close();
  }, []);

  useEffect(() => {
    connect();
    return () => wsRef.current?.close();
  }, [connect]);

  return { connected };
}
