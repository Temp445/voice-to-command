'use client';

import { useEffect, useRef } from 'react';
import { useSettingsStore } from '@/store/settingsStore';
import { api } from '@/lib/api';
import { useToastStore } from '@/store/toastStore';

export function ShortcutManager() {
  const overlayShortcut = useSettingsStore(s => s.overlayShortcut);
  const listenShortcut = useSettingsStore(s => s.listenShortcut);
  const updateSettings = useSettingsStore(s => s.update);
  const registeredRef = useRef<{ overlay?: string, listen?: string }>({});
  const registrationSeqRef = useRef(0);

  useEffect(() => {
    // If we are in a web browser (not Tauri), use a local fallback listener
    if (!(window as any).__TAURI__) {
      const handleKeyDown = (e: KeyboardEvent) => {
        const checkShortcut = (shortcut: string | undefined) => {
          if (!shortcut) return false;
          const parts = shortcut.toLowerCase().split('+');
          const key = parts.pop();
          
          const needAlt = parts.includes('alt');
          const needShift = parts.includes('shift');
          const needCtrlMeta = parts.some(p => p === 'ctrl' || p === 'control' || p === 'command' || p === 'commandorcontrol' || p === 'meta');
          
          if (!e.key) return false;
          let matchKey = e.key.toLowerCase();
          if (e.code === 'Space') matchKey = 'space';
          
          if (matchKey !== key) return false;
          if (needAlt !== e.altKey) return false;
          if (needShift !== e.shiftKey) return false;
          
          const hasCtrlMeta = e.ctrlKey || e.metaKey;
          if (needCtrlMeta !== hasCtrlMeta) return false;
          
          return true;
        };

        if (checkShortcut(overlayShortcut)) {
          e.preventDefault();
          const currentState = useSettingsStore.getState().enableDesktopOverlay;
          const newState = !currentState;
          updateSettings({ enableDesktopOverlay: newState });
          api.updateSettings({ enable_desktop_overlay: newState }).catch(console.error);
        }

        if (checkShortcut(listenShortcut)) {
          e.preventDefault();
          api.activate().catch(console.error);
        }
      };

      window.addEventListener('keydown', handleKeyDown);
      return () => window.removeEventListener('keydown', handleKeyDown);
    }

    const seq = ++registrationSeqRef.current;

    async function registerShortcuts() {
      try {
        let tauriShortcut;
        try {
          tauriShortcut = await import('@tauri-apps/plugin-global-shortcut');
        } catch (e) {
          console.warn("Tauri shortcut plugin import failed (likely HMR), skipping registration.", e);
          return;
        }
        const { register, unregisterAll } = tauriShortcut;
        
        // Always unregister all previous shortcuts before registering new ones
        // This is robust against Next.js Fast Refresh which might leave stale hotkeys registered
        await unregisterAll().catch(console.warn);
        
        // If a newer registration has started, abort this one
        if (seq !== registrationSeqRef.current) return;

        registeredRef.current = {};

        // Overlay Toggle
        if (overlayShortcut) {
          try {
            await register(overlayShortcut, () => {
               // Fetch latest state to toggle
               const currentState = useSettingsStore.getState().enableDesktopOverlay;
               const newState = !currentState;
               updateSettings({ enableDesktopOverlay: newState });
               api.updateSettings({ enable_desktop_overlay: newState }).catch(console.error);
            });
            if (seq === registrationSeqRef.current) {
              registeredRef.current.overlay = overlayShortcut;
            }
          } catch (e: any) {
            console.warn("Failed to register overlay shortcut:", e);
            useToastStore.getState().toast({
              title: "Overlay Shortcut Conflict",
              description: `Failed to register "${overlayShortcut}". The hotkey may be in use by another application.`,
              type: "error"
            });
          }
        }

        // If a newer registration started while registering overlay, abort
        if (seq !== registrationSeqRef.current) return;

        // Trigger Listen
        if (listenShortcut) {
          try {
            await register(listenShortcut, async () => {
               await api.activate().catch(e => console.warn("Failed to activate listen:", e));
            });
            if (seq === registrationSeqRef.current) {
              registeredRef.current.listen = listenShortcut;
            }
          } catch (e: any) {
            console.warn("Failed to register listen shortcut:", e);
            useToastStore.getState().toast({
              title: "Listen Shortcut Conflict",
              description: `Failed to register "${listenShortcut}". The hotkey may be in use by another application.`,
              type: "error"
            });
          }
        }

      } catch (err) {
        console.warn("GlobalShortcut API not available or error:", err);
      }
    }

    registerShortcuts();

    return () => {
      // If no new registration has started (seq is still the latest), then we are unmounting or changing shortcuts.
      // Increment the sequence to cancel any pending registration from the current effect.
      if (seq === registrationSeqRef.current) {
        registrationSeqRef.current++;
        
        try {
          import('@tauri-apps/plugin-global-shortcut').then(({ unregisterAll }) => {
            // Double check if a newer sequence has started in the meantime
            if (registrationSeqRef.current === seq + 1) {
              unregisterAll().catch(console.warn);
              registeredRef.current = {};
            }
          }).catch(() => {});
        } catch (e) {
          // Ignore synchronous import errors during HMR
        }
      }
    };
  }, [overlayShortcut, listenShortcut, updateSettings]);

  return null; // Invisible component
}
