// Zustand settings store
import { create } from "zustand";

interface SettingsStore {
  wakeWord: string;
  sttProvider: "whisper" | "gstt" | "elevenlabs" | "deepgram";
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
  replySound: boolean;
  speechRate: number;
  screenSettingsVisibleToUsers: boolean;
  role: string;
  permissions: Record<string, { visible: boolean; mutable: boolean }>;
  
  // ElevenLabs
  elevenlabsApiKey: string;
  elevenlabsConfigured: boolean;

  // Deepgram
  deepgramApiKey: string;
  deepgramConfigured: boolean;

  // CRM Integration
  crmUrl: string;       // legacy: first site URL (kept for backward compat)
  crmKeywords: string;  // legacy: first site keywords
  crmSites: Array<{ url: string; keywords: string }>;
  restrictBrowserAutomation: boolean;

  // LLM
  llmEnabled: boolean;
  llmProvider: string;
  llmModel: string;
  llmApiKey: string;
  llmMode: "fallback" | "always_on";
  llmTemperature: number;
  llmSystemError: string | null;

  // Scanning
  scanMode: "auto" | "manual";

  setTtsProvider: (p: "piper" | "gtts") => void;
  update: (patch: Partial<SettingsStore>) => void;
  resetSettings: () => void;
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

export const useSettingsStore = create<SettingsStore>((set) => ({
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
  replySound: true,
  speechRate: 1.0,
  screenSettingsVisibleToUsers: true,
  role: "user",
  permissions: {},

  // CRM / Website Shortcuts (empty by default — users add their own)
  crmUrl:         "",
  crmKeywords:    "",
  crmSites:       [],
  restrictBrowserAutomation: true,

  // LLM Defaults
  llmEnabled:     true,
  llmProvider:    "groq",
  llmModel:       "llama-3.3-70b-versatile",
  llmApiKey:      "",
  llmMode:        "fallback",
  llmTemperature: 0.7,
  llmSystemError: null,

  // Scanning
  scanMode:       "manual",

  // ElevenLabs
  elevenlabsApiKey: "",
  elevenlabsConfigured: false,

  // Deepgram
  deepgramApiKey: "",
  deepgramConfigured: false,

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
  resetSettings: () => set({
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
    replySound: true,
    speechRate: 1.0,
    screenSettingsVisibleToUsers: true,
    role: "user",
    permissions: {},

    // CRM / Website Shortcuts
    crmUrl:         "",
    crmKeywords:    "",
    crmSites:       [],
    restrictBrowserAutomation: false,

    // LLM Defaults
    llmEnabled:     true,
    llmProvider:    "groq",
    llmModel:       "llama-3.3-70b-versatile",
    llmApiKey:      "",
    llmMode:        "fallback",
    llmTemperature: 0.7,
    llmSystemError: null,

    // Scanning
    scanMode:       "manual",

    // ElevenLabs
    elevenlabsApiKey: "",
    elevenlabsConfigured: false,

    // Deepgram
    deepgramApiKey: "",
    deepgramConfigured: false,
  }),
}));

