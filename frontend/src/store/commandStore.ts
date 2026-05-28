// Zustand command history store
import { create } from "zustand";

export interface CommandEntry {
  id: string;
  raw_text: string;
  intent?: string;
  parameters?: Record<string, unknown>;
  status: "pending" | "running" | "success" | "failed";
  result?: string;
  source: "voice" | "text";
  duration_ms?: number;
  executed_at?: string;
}

interface CommandStore {
  history: CommandEntry[];
  pending: string | null;
  addEntry: (entry: CommandEntry) => void;
  updateEntry: (id: string, patch: Partial<CommandEntry>) => void;
  setPending: (text: string | null) => void;
  clear: () => void;
}

export const useCommandStore = create<CommandStore>((set) => ({
  history: [],
  pending: null,

  addEntry: (entry) =>
    set((s) => ({ history: [entry, ...s.history].slice(0, 500) })),

  updateEntry: (id, patch) =>
    set((s) => ({
      history: s.history.map((e) => (e.id === id ? { ...e, ...patch } : e)),
    })),

  setPending: (text) => set({ pending: text }),
  clear:      () => set({ history: [] }),
}));
