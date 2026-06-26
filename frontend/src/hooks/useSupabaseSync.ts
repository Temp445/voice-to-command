import { useEffect } from 'react';
import { supabase } from '@/lib/supabase';
import { useAuthStore } from '@/store/authStore';
import { useSettingsStore } from '@/store/settingsStore';
import { api } from '@/lib/api';

/**
 * Listens to Supabase Realtime events (Inserts, Updates, Deletions)
 * and automatically synchronizes the local frontend and backend states.
 */
export function useSupabaseSync() {
  const { session } = useAuthStore();
  const updateSettings = useSettingsStore((state) => state.update);

  useEffect(() => {
    if (!session?.user?.id) return;

    // Create a realtime subscription channel for the settings table
    const channel = supabase
      .channel('settings_sync')
      .on(
        'postgres_changes',
        {
          event: '*', // Listen for INSERT, UPDATE, and DELETE
          schema: 'public',
          table: 'settings',
          filter: `user_id=eq.${session.user.id}`
        },
        async (payload) => {
          console.log('[Supabase Realtime] Settings change detected:', payload.eventType);
          
          try {
            // By fetching from the backend API instead of just updating the local store,
            // we guarantee that the backend (FastAPI) also gets the updated settings
            // and hot-reloads its internal configurations (like LLM, TTS, etc.).
            const data: any = await api.getSettings();
            
            // Map snake_case API response to camelCase store keys
            updateSettings({
              wakeWord: data.wake_word, 
              sttProvider: data.stt_provider, 
              sttNoiseCancellation: data.stt_noise_cancellation,
              whisperModel: data.whisper_model, 
              ttsProvider: data.tts_provider, 
              piperVoice: data.piper_voice,
              activeModeTimeout: data.active_mode_timeout, 
              requireWakeWordAlways: data.require_wake_word_always,
              browserType: data.browser_type, 
              startupOnBoot: data.startup_on_boot, 
              minimizeToTray: data.minimize_to_tray,
              theme: data.theme, 
              browserAnimationsEnabled: data.browser_animations_enabled, 
              enableDesktopOverlay: data.enable_desktop_overlay,
              crmUrl: data.crm_url, 
              crmKeywords: data.crm_keywords,
              crmSites: (() => {
                try { return JSON.parse(data.crm_sites || "[]") || []; } catch { return []; }
              })(),
              restrictBrowserAutomation: data.restrict_browser_automation || false,
              llmEnabled: data.llm_enabled, 
              llmProvider: data.llm_provider, 
              llmModel: data.llm_model,
              llmMode: data.llm_mode, 
              llmTemperature: data.llm_temperature,
              scanMode: (data.scan_mode as "auto" | "manual") || "manual",
              replySound: data.reply_sound !== undefined ? data.reply_sound : true,
              speechRate: data.speech_rate !== undefined ? data.speech_rate : 1.0,
            });
            console.log('[Supabase Realtime] Local settings perfectly synchronized.');
          } catch (e) {
            console.error('[Supabase Realtime] Failed to sync settings after change:', e);
          }
        }
      )
      .subscribe((status) => {
        if (status === 'SUBSCRIBED') {
          console.log('[Supabase Realtime] Actively listening for database changes...');
        }
      });

    return () => {
      // Clean up the subscription when the user logs out or the component unmounts
      supabase.removeChannel(channel);
    };
  }, [session?.user?.id, updateSettings]);
}
