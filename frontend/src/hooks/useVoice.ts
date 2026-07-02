"use client";

import { useCallback } from "react";
import { api } from "@/lib/api";
import { useCommandStore } from "@/store/commandStore";
import { useVoiceStore } from "@/store/voiceStore";

export function useVoice() {
  const { addEntry, updateEntry } = useCommandStore();
  const { setPipelineState } = useVoiceStore();

  const activate = useCallback(async () => {
    try {
      setPipelineState("listening");
      await api.activate();
    } catch (e) {
      setPipelineState("error");
    }
  }, []);

  const deactivate = useCallback(async () => {
    await api.deactivate();
    setPipelineState("idle");
  }, []);

  const executeText = useCallback(async (text: string) => {
    const tempId = crypto.randomUUID();
    addEntry({ id: tempId, raw_text: text, status: "running", source: "text" });
    try {
      const result = await api.executeCommand(text, "text", tempId) as any;
      updateEntry(tempId, { ...result, source: "text" });
    } catch (e: any) {
      const msg = String(e);
      const isAuthError = msg.includes("401") || msg.toLowerCase().includes("not authenticated") || msg.toLowerCase().includes("unauthorized");
      updateEntry(tempId, {
        status: "failed",
        result: isAuthError
          ? "⚠️ Not logged in — please sign in to execute commands."
          : msg,
        source: "text",
      });
    }
  }, []);

  return { activate, deactivate, executeText };
}
