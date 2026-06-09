// Zustand settings store
import { create } from "zustand";
import { persist } from "zustand/middleware";

interface SettingsStore {
  wakeWord: string;
  sttProvider: "whisper" | "gstt";
  sttNoiseCancellation: boolean;
  whisperModel: "tiny" | "base" | "small" | "large-v2" | "large-v3";
  activeModeTimeout: number;
  ttsProvider: "piper" | "gtts";
  piperVoice: string;
  theme: "dark" | "light";
  browserType: "chromium" | "firefox" | "webkit";
  startupOnBoot: boolean;
  minimizeToTray: boolean;
  browserAnimationsEnabled: boolean;
  enableDesktopOverlay: boolean;
  
  // CRM Integration
  crmUrl: string;
  crmKeywords: string;

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

/** Push the persisted minimizeToTray value to the Rust backend on startup */
export function syncTrayStateOnBoot(minimizeToTray: boolean) {
  import("@tauri-apps/api").then(({ invoke }) => {
    invoke("sync_minimize_to_tray", { value: minimizeToTray }).catch(console.error);
  }).catch(() => {/* not in Tauri context (web dev) */});
}

export const useSettingsStore = create<SettingsStore>()(
  persist(
    (set) => ({
      wakeWord:       "alexa",
      sttProvider:    "whisper",
      sttNoiseCancellation: true,
      whisperModel:   "base",
      activeModeTimeout: 120,
      ttsProvider:    "piper",
      piperVoice:     "en_US-lessac-medium",
      theme:          "dark",
      browserType:    "chromium",
      startupOnBoot:  true,
      minimizeToTray: true,
      browserAnimationsEnabled: true,
      enableDesktopOverlay: true,

      // CRM Defaults
      crmUrl:         "https://crm.acesoftcloud.in/",
      crmKeywords:    "open my crm, open crm, open ace crm",

      // LLM Defaults
      llmEnabled:     true,
      llmProvider:    "groq",
      llmModel:       "llama-3.3-70b-versatile",
      llmApiKey:      "",
      llmMode:        "fallback",
      llmTemperature: 0.7,

      setTtsProvider: (p) => set({ ttsProvider: p }),
      update: (patch) => {
        set(patch);
        // Sync tray state to Rust backend whenever it changes
        if (patch.minimizeToTray !== undefined) {
          import("@tauri-apps/api").then(({ invoke }) => {
            invoke("sync_minimize_to_tray", { value: patch.minimizeToTray }).catch(console.error);
          }).catch(() => {});
        }
      },
    }),
    { name: "ace-settings" }
  )
);
