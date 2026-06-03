"use client";

import { motion } from "framer-motion";
import { Code, Globe, Folder, Terminal, Volume2, Monitor, Search, Lock } from "lucide-react";
import { useVoice } from "@/hooks/useVoice";

const ACTIONS = [
  { label: "VS Code",    cmd: "open vs code",          icon: Code,     color: "#6366f1" },
  { label: "Search",     cmd: "search google",          icon: Search,   color: "#3b82f6" },
  { label: "Downloads",  cmd: "open folder downloads",  icon: Folder,   color: "#f59e0b" },
  { label: "Terminal",   cmd: "open terminal",           icon: Terminal, color: "#22c55e" },
  { label: "YouTube",    cmd: "open youtube.com",        icon: Globe,    color: "#ef4444" },
  { label: "Volume Up",  cmd: "volume up",               icon: Volume2,  color: "#8b5cf6" },
  { label: "Screenshot", cmd: "take a screenshot",       icon: Monitor,  color: "#06b6d4" },
  { label: "Lock",       cmd: "lock screen",             icon: Lock,     color: "#9CA3AF" },
];

export function QuickActions() {
  const { executeText } = useVoice();

  return (
    <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: "1rem", padding: "1.25rem" }}>
      <p style={{ fontSize: "0.8125rem", fontWeight: 600, color: "var(--foreground)", marginBottom: "0.875rem" }}>Quick Actions</p>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "0.625rem" }}>
        {ACTIONS.map(({ label, cmd, icon: Icon, color }, i) => (
          <motion.button
            key={cmd}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.04 }}
            whileHover={{ scale: 1.03, y: -1 }}
            whileTap={{ scale: 0.97 }}
            onClick={() => executeText(cmd)}
            style={{
              display: "flex", flexDirection: "column", alignItems: "center", gap: "0.5rem",
              padding: "0.875rem 0.375rem", borderRadius: "0.625rem",
              background: "var(--secondary)", border: "1px solid var(--border)",
              cursor: "pointer", transition: "all 0.15s ease",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = "var(--muted)";
              (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--ring)";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = "var(--secondary)";
              (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--border)";
            }}
          >
            <div style={{ width: "2rem", height: "2rem", borderRadius: "0.5rem", background: `${color}18`, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <Icon style={{ width: "1rem", height: "1rem", color }} />
            </div>
            <span style={{ fontSize: "0.6875rem", color: "var(--muted-foreground)", textAlign: "center", lineHeight: 1.2 }}>{label}</span>
          </motion.button>
        ))}
      </div>
    </div>
  );
}