import { create } from "zustand";
import { Session, User } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabase";
import { api } from "@/lib/api";
import { useSettingsStore } from "@/store/settingsStore";
import { useChatStore } from "@/store/chatStore";
import { useCommandStore } from "@/store/commandStore";

interface AuthState {
  session: Session | null;
  user: User | null;
  loading: boolean;
  setSession: (session: Session | null) => void;
  setUser: (user: User | null) => void;
  setLoading: (loading: boolean) => void;
  signOut: () => Promise<void>;
  initializeAuth: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  session: null,
  user: null,
  loading: true,
  setSession: (session) => set({ session }),
  setUser: (user) => set({ user }),
  setLoading: (loading) => set({ loading }),
  signOut: async () => {
    await supabase.auth.signOut();
    set({ session: null, user: null });
    
    // Clear all user-related state and localStorage
    useSettingsStore.getState().resetSettings();
    useChatStore.getState().clear();
    useCommandStore.getState().clear();
    try {
      localStorage.removeItem("ace-local-token");
      localStorage.removeItem("ace-settings");
      localStorage.removeItem("chat-history-storage");
      localStorage.removeItem("command-history-storage");
    } catch (e) {}
  },
  initializeAuth: () => {
    const syncWithBackend = async (token: string, retries = 5, delay = 1000) => {
      try {
        const response: any = await api.sync(token);
        localStorage.setItem("ace-local-token", response.access_token);
      } catch (e) {
        if (retries > 0) {
          setTimeout(() => syncWithBackend(token, retries - 1, delay * 2), delay);
        } else {
          console.error("Failed to sync auth with backend after all retries", e);
        }
      }
    };

    supabase.auth.getSession().then(({ data: { session } }) => {
      set({ session, user: session?.user ?? null, loading: false });
      if (session) syncWithBackend(session.access_token);
    });

    supabase.auth.onAuthStateChange((_event, session) => {
      set({ session, user: session?.user ?? null, loading: false });
      if (session) {
        syncWithBackend(session.access_token);
      } else {
        // Clear all user-related state and localStorage on logout/expiry
        useSettingsStore.getState().resetSettings();
        useChatStore.getState().clear();
        useCommandStore.getState().clear();
        try {
          localStorage.removeItem("ace-local-token");
          localStorage.removeItem("ace-settings");
          localStorage.removeItem("chat-history-storage");
          localStorage.removeItem("command-history-storage");
        } catch (e) {}
      }
    });
  },
}));

