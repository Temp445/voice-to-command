"use client";
import { useEffect } from "react";
import { useSettingsStore, syncTrayStateOnBoot } from "@/store/settingsStore";

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const theme = useSettingsStore((s) => s.theme);
  const minimizeToTray = useSettingsStore((s) => s.minimizeToTray);

  // Sync theme on change
  useEffect(() => {
    const root = window.document.documentElement;
    root.classList.remove("light", "dark");
    root.classList.add(theme);
  }, [theme]);

  // Sync minimizeToTray to Rust backend on startup.
  // Rust initializes AppState with `true`, but the user's persisted setting
  // may be `false` — so we push the real value on every app load.
  useEffect(() => {
    syncTrayStateOnBoot(minimizeToTray);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // intentionally run once on mount

  return <>{children}</>;
}
