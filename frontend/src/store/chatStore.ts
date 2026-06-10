import { create } from "zustand";
import { persist } from "zustand/middleware";
import { ChatMessage } from "@/hooks/useLLMChat";

interface ChatStore {
  messages: ChatMessage[];
  addMessage: (msg: ChatMessage) => void;
  updateMessage: (id: string, content: string) => void;
  setMessages: (messages: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => void;
  clear: () => void;
}

export const useChatStore = create<ChatStore>()(
  persist(
    (set) => ({
      messages: [],
      addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
      updateMessage: (id, content) =>
        set((s) => ({
          messages: s.messages.map((m) => (m.id === id ? { ...m, content } : m)),
        })),
      setMessages: (updater) =>
        set((s) => ({
          messages: typeof updater === "function" ? updater(s.messages) : updater,
        })),
      clear: () => set({ messages: [] }),
    }),
    {
      name: "chat-history-storage",
    }
  )
);
