// Zustand settings store
import { create } from "zustand";
import { persist } from "zustand/middleware";

interface SettingsStore {
  wakeWord: string;
  sttProvider: "whisper" | "gstt";
  sttNoiseCancellation: boolean;
  whisperModel: "tiny" | "base" | "small" | "medium";
  activeModeTimeout: number;
  requireWakeWordAlways: boolean;
  ttsProvider: "piper" | "gtts";
  piperVoice: string;
  theme: "dark" | "light";
  browserType: "chromium" | "firefox" | "webkit";
  startupOnBoot: boolean;
  minimizeToTray: boolean;
  browserAnimationsEnabled: boolean;
  enableDesktopOverlay: boolean;
  overlayShortcut: string;
  listenShortcut: string;
  
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
  llmSystemError: string | null;

  setTtsProvider: (p: "piper" | "gtts") => void;
  update: (patch: Partial<SettingsStore>) => void;
}

/** Push the persisted minimizeToTray value to the Rust backend on startup */
export function syncTrayStateOnBoot(minimizeToTray: boolean) {
  if (typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__) {
    import("@tauri-apps/api/core").then((tauriCore) => {
      if (tauriCore && typeof tauriCore.invoke === "function") {
        tauriCore.invoke("sync_minimize_to_tray", { value: minimizeToTray }).catch(console.error);
      }
    }).catch(() => {/* not in Tauri context (web dev) */});
  }
}

export const useSettingsStore = create<SettingsStore>()(
  persist(
    (set) => ({
      wakeWord:       "alexa",
      sttProvider:    "whisper",
      sttNoiseCancellation: true,
      whisperModel:   "base",
      activeModeTimeout: 120,
      requireWakeWordAlways: true,
      ttsProvider:    "piper",
      piperVoice:     "en_US-lessac-medium",
      theme:          "dark",
      browserType:    "chromium",
      startupOnBoot:  true,
      minimizeToTray: true,
      browserAnimationsEnabled: true,
      enableDesktopOverlay: true,
      overlayShortcut: "Alt+A",
      listenShortcut: "Alt+S",

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
      llmSystemError: null,

      setTtsProvider: (p) => set({ ttsProvider: p }),
      update: (patch) => {
        set(patch);
        // Sync tray state to Rust backend whenever it changes
        if (patch.minimizeToTray !== undefined) {
          if (typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__) {
            import("@tauri-apps/api/core").then((tauriCore) => {
              if (tauriCore && typeof tauriCore.invoke === "function") {
                tauriCore.invoke("sync_minimize_to_tray", { value: patch.minimizeToTray }).catch(console.error);
              }
            }).catch(() => {});
          }
        }
      },
    }),
    { name: "ace-settings" }
  )
);
