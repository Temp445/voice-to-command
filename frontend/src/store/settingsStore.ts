// Zustand settings store
import { create } from "zustand";
import { persist } from "zustand/middleware";

interface SettingsStore {
  wakeWord: string;
  whisperModel: "tiny" | "base" | "small";
  ttsProvider: "piper" | "gtts";
  piperVoice: string;
  theme: "dark" | "light";
  browserType: "chromium" | "firefox" | "webkit";
  startupOnBoot: boolean;
  minimizeToTray: boolean;
  
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
      whisperModel:   "base",
      ttsProvider:    "piper",
      piperVoice:     "en_US-lessac-medium",
      theme:          "dark",
      browserType:    "chromium",
      startupOnBoot:  true,
      minimizeToTray: true,

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
