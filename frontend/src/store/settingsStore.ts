// Zustand settings store
import { create } from "zustand";
import { persist } from "zustand/middleware";

interface SettingsStore {
  wakeWord: string;
  sttProvider: "whisper" | "gstt";
  sttNoiseCancellation: boolean;
  whisperModel: "tiny" | "base" | "small" | "large-v2" | "large-v3";
  ttsProvider: "piper" | "gtts";
  piperVoice: string;
  theme: "dark" | "light";
  browserType: "chromium" | "firefox" | "webkit";
  startupOnBoot: boolean;
  minimizeToTray: boolean;
  browserAnimationsEnabled: boolean;
  enableDesktopOverlay: boolean;
  
  // LLM
  llmEnabled: boolean;
  llmProvider: string;
  llmModel: string;
  llmApiKey: string;
  llmMode: "fallback" | "always_on";
  llmTemperature: number;

  setTtsProvider: (p: "piper" | "gtts") => void;
  update: (patch: Partial<SettingsStore>) => void;
}

export const useSettingsStore = create<SettingsStore>()(
  persist(
    (set) => ({
      wakeWord:       "alexa",
      sttProvider:    "whisper",
      sttNoiseCancellation: true,
      whisperModel:   "base",
      ttsProvider:    "piper",
      piperVoice:     "en_US-lessac-medium",
      theme:          "dark",
      browserType:    "chromium",
      startupOnBoot:  true,
      minimizeToTray: true,
      browserAnimationsEnabled: true,
      enableDesktopOverlay: true,

      // LLM Defaults
      llmEnabled:     true,
      llmProvider:    "groq",
      llmModel:       "llama-3.3-70b-versatile",
      llmApiKey:      "",
      llmMode:        "fallback",
      llmTemperature: 0.7,

      setTtsProvider: (p) => set({ ttsProvider: p }),
      update:         (patch) => set(patch),
    }),
    { name: "ace-settings" }
  )
);
