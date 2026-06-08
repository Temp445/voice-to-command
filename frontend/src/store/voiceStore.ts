// Zustand voice state store
import { create } from "zustand";

type PipelineState = "idle" | "listening" | "processing" | "speaking" | "error";

interface VoiceStore {
  pipelineState: PipelineState;
  isListening: boolean;
  transcript: string;
  partialTranscript: string;
  wakeWordActive: boolean;
  ttsProvider: "piper" | "gtts";
  whisperModel: string;
  sidebarCollapsed: boolean;

  setPipelineState: (state: PipelineState) => void;
  setListening: (v: boolean) => void;
  setTranscript: (text: string, isFinal: boolean) => void;
  setWakeWordActive: (v: boolean) => void;
  setTtsProvider: (p: "piper" | "gtts") => void;
  setSidebarCollapsed: (v: boolean) => void;
  reset: () => void;
}

export const useVoiceStore = create<VoiceStore>((set) => ({
  pipelineState:    "idle",
  isListening:      false,
  transcript:       "",
  partialTranscript:"",
  wakeWordActive:   false,
  ttsProvider:      "piper",
  whisperModel:     "base",
  sidebarCollapsed: true,

  setPipelineState: (state) => set({ pipelineState: state, isListening: state === "listening" }),
  setListening:     (v) => set({ isListening: v }),
  setTranscript:    (text, isFinal) =>
    isFinal
      ? set({ transcript: text, partialTranscript: "" })
      : set({ partialTranscript: text }),
  setWakeWordActive: (v) => set({ wakeWordActive: v }),
  setTtsProvider:    (p) => set({ ttsProvider: p }),
  setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),
  reset:            () => set({ pipelineState: "idle", isListening: false, partialTranscript: "" }),
}));
