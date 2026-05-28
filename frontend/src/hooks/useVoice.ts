"use client";

import { useCallback } from "react";
import { api } from "@/lib/api";
import { useCommandStore } from "@/store/commandStore";
import { useVoiceStore } from "@/store/voiceStore";

export function useVoice() {
  const { addEntry } = useCommandStore();
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
      const result = await api.executeCommand(text) as any;
      addEntry({ ...result, source: "text" });
    } catch (e) {
      addEntry({ id: tempId, raw_text: text, status: "failed", result: String(e), source: "text" });
    }
  }, []);

  return { activate, deactivate, executeText };
}
