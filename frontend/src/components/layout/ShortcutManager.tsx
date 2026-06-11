'use client';

import { useEffect, useRef } from 'react';
import { useSettingsStore } from '@/store/settingsStore';
import { api } from '@/lib/api';

export function ShortcutManager() {
  const overlayShortcut = useSettingsStore(s => s.overlayShortcut);
  const listenShortcut = useSettingsStore(s => s.listenShortcut);
  const updateSettings = useSettingsStore(s => s.update);
  const registeredRef = useRef<{ overlay?: string, listen?: string }>({});

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
    async function registerShortcuts() {
      try {
        const { register, unregisterAll, unregister } = await import('@tauri-apps/api/globalShortcut');
        
        // Always unregister previous shortcuts before registering new ones
        if (registeredRef.current.overlay) await unregister(registeredRef.current.overlay).catch(console.error);
        if (registeredRef.current.listen) await unregister(registeredRef.current.listen).catch(console.error);
        
        registeredRef.current = {};

        // Overlay Toggle
        if (overlayShortcut) {
          await register(overlayShortcut, () => {
             // Fetch latest state to toggle
             const currentState = useSettingsStore.getState().enableDesktopOverlay;
             const newState = !currentState;
             updateSettings({ enableDesktopOverlay: newState });
             api.updateSettings({ enable_desktop_overlay: newState }).catch(console.error);
          }).catch(e => console.error("Failed to register overlay shortcut:", e));
          registeredRef.current.overlay = overlayShortcut;
        }

        // Trigger Listen
        if (listenShortcut) {
          await register(listenShortcut, async () => {
             await api.activate().catch(e => console.error("Failed to activate listen:", e));
          }).catch(e => console.error("Failed to register listen shortcut:", e));
          registeredRef.current.listen = listenShortcut;
        }

      } catch (err) {
        console.error("GlobalShortcut API not available or error:", err);
      }
    }

    registerShortcuts();

    return () => {
      // Cleanup on unmount (or when shortcuts change)
      if ((window as any).__TAURI__) {
        import('@tauri-apps/api/globalShortcut').then(({ unregisterAll }) => {
          unregisterAll().catch(console.error);
          registeredRef.current = {};
        }).catch(() => {});
      }
    };
  }, [overlayShortcut, listenShortcut, updateSettings]);

  return null; // Invisible component
}
