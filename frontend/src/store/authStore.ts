import { create } from "zustand";
import { Session, User } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabase";
import { api } from "@/lib/api";

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
  },
  initializeAuth: () => {
    const syncWithBackend = async (token: string) => {
      try {
        const response: any = await api.sync(token);
        localStorage.setItem("ace-local-token", response.access_token);
      } catch (e) {
        console.error("Failed to sync auth with backend", e);
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
        localStorage.removeItem("ace-local-token");
      }
    });
  },
}));
