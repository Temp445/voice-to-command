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

  setTtsProvider: (p: "piper" | "gtts") => void;
  update: (patch: Partial<SettingsStore>) => void;
}

export const useSettingsStore = create<SettingsStore>()(
  persist(
    (set) => ({
      wakeWord:       "hey ace",
      whisperModel:   "base",
      ttsProvider:    "piper",
      piperVoice:     "en_US-lessac-medium",
      theme:          "dark",
      browserType:    "chromium",
      startupOnBoot:  true,
      minimizeToTray: true,

      setTtsProvider: (p) => set({ ttsProvider: p }),
      update:         (patch) => set(patch),
    }),
    { name: "ace-settings" }
  )
);
