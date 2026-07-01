"use client";

import { useEffect, useRef, useCallback } from "react";
import { useVoiceStore } from "@/store/voiceStore";
import { useCommandStore } from "@/store/commandStore";
import { create } from "zustand";
import { useSettingsStore } from "@/store/settingsStore";
import { getBackendWsUrl } from "@/lib/api";
import { useAuthStore } from "@/store/authStore";

interface WSStore { 
  connected: boolean; 
  setConnected: (v: boolean) => void; 
  sendBytes: (data: ArrayBuffer | ArrayBufferView) => void;
  setSendBytes: (fn: (data: ArrayBuffer | ArrayBufferView) => void) => void;
  // Scan tracking
  scanLastAt: string | null;
  scanAppCount: number | null;
  setScanResult: (timestamp: string, appCount: number) => void;
  // Active tab state
  activeTabTitle: string | null;
  activeTabUrl: string | null;
  setActiveTab: (title: string | null, url: string | null) => void;
}
export const useWSStore = create<WSStore>((set) => ({
  connected: false,
  setConnected: (v) => set({ connected: v }),
  sendBytes: () => {},
  setSendBytes: (fn) => set({ sendBytes: fn }),
  scanLastAt: null,
  scanAppCount: null,
  setScanResult: (timestamp, appCount) => set({ scanLastAt: timestamp, scanAppCount: appCount }),
  activeTabTitle: null,
  activeTabUrl: null,
  setActiveTab: (title, url) => set({ activeTabTitle: title, activeTabUrl: url }),
}));

export function WebSocketManager() {
  const wsRef = useRef<WebSocket | null>(null);
  const { setPipelineState, setTranscript, setWakeWordActive } = useVoiceStore();
  const { addEntry, updateEntry } = useCommandStore();
    const { connected, setConnected, setSendBytes } = useWSStore();
    const { user } = useAuthStore();

    const connect = useCallback(async () => {
      if (wsRef.current?.readyState === WebSocket.OPEN) return;

      const wsUrl = await getBackendWsUrl();

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (wsRef.current !== ws) return;
        setConnected(true);
        setSendBytes((data) => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(data);
          }
        });
        console.log("✅ WebSocket connected");
        
        // Send initial auth sync message directly on open
        const user = useAuthStore.getState().user;
        ws.send(JSON.stringify({
          type: "auth_sync",
          user_id: user?.id || null
        }));
        console.log("📤 Sent auth_sync via WebSocket onopen:", user?.id || "logged-out");
      };

    ws.onmessage = (e) => {
      try {
        const { event, data } = JSON.parse(e.data);
        switch (event) {
          case "connected":
            if (data && data.active_tab) {
              useWSStore.getState().setActiveTab(data.active_tab.title, data.active_tab.url);
            }
            break;
          case "tab_changed":
            useWSStore.getState().setActiveTab(data.title, data.url);
            break;
          case "pipeline_state":
            setPipelineState(data.state);
            if (data.wake_word_active !== undefined) {
              setWakeWordActive(data.wake_word_active);
            }
            break;
          case "transcript":
            console.log("🎙️ Received transcript from backend:", data.text, "is_final:", data.is_final);
            setTranscript(data.text, data.is_final);
            break;
          case "command_executed":
            const state = useCommandStore.getState();
            if (state.history.some(e => e.id === data.id)) {
              state.updateEntry(data.id, { ...data, source: data.source || "voice" });
            } else {
              state.addEntry({ ...data, source: data.source || "voice" });
            }
            break;
          case "wake_word_detected":
            setWakeWordActive(true);
            setTimeout(() => setWakeWordActive(false), 2000);
            break;
          case "settings_updated":
            const updatePayload: any = {};
            if (data.enable_desktop_overlay !== undefined) updatePayload.enableDesktopOverlay = data.enable_desktop_overlay;
            if (data.wake_word !== undefined) updatePayload.wakeWord = data.wake_word;
            if (data.tts_provider !== undefined) updatePayload.ttsProvider = data.tts_provider;
            
            if (Object.keys(updatePayload).length > 0) {
              useSettingsStore.getState().update(updatePayload);
            }
            break;
          case "system_error":
            useSettingsStore.getState().update({ llmSystemError: data.error });
            break;
          case "scan_complete":
            useWSStore.getState().setScanResult(data.timestamp, data.app_count);
            break;
        }
      } catch {}
    };

    ws.onclose = () => {
      if (wsRef.current === ws) {
        setConnected(false);
        if (isMounted.current) {
          setTimeout(connect, 3000);
        }
      }
    };

    ws.onerror = () => ws.close();
  }, []);

  useEffect(() => {
    if (connected && wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: "auth_sync",
        user_id: user?.id || null
      }));
      console.log("📤 Sent auth_sync via WebSocket:", user?.id || "logged-out");
    }
  }, [user, connected]);

  const isMounted = useRef(true);
  useEffect(() => {
    isMounted.current = true;
    connect();
    return () => {
      isMounted.current = false;
      wsRef.current?.close();
    };
  }, [connect]);

  return null;
}

export function useWebSocket() {
  const { connected, activeTabTitle, activeTabUrl } = useWSStore();
  return { connected, activeTabTitle, activeTabUrl };
}
