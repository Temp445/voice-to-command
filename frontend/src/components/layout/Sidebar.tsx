"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { LayoutDashboard, Terminal, GitBranch, Activity, Settings, Mic, ChevronLeft, ChevronRight, Zap, Bot, History } from "lucide-react";
import { useState } from "react";
import { useVoiceStore } from "@/store/voiceStore";

const NAV_ITEMS = [
  { href: "/",           icon: LayoutDashboard, label: "Dashboard"  },
  { href: "/chat",       icon: Bot,              label: "Chat"       },
  { href: "/console",    icon: Terminal,         label: "Console"    },
  { href: "/history",    icon: History,          label: "History"    },
  // { href: "/workflows",  icon: GitBranch,        label: "Workflows"  },
  // { href: "/automation", icon: Activity,         label: "Automation" },
  { href: "/settings",   icon: Settings,         label: "Settings"   },
];

const STATE_COLOR: Record<string, string> = {
  idle:       "var(--state-idle)",
  listening:  "var(--state-listening)",
  processing: "var(--state-processing)",
  speaking:   "var(--state-speaking)",
  error:      "var(--state-error)",
};

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const { pipelineState } = useVoiceStore();

  const stateColor = STATE_COLOR[pipelineState] || STATE_COLOR.idle;

  return (
    <motion.aside
      className="glass-strong"
      style={{ display: "flex", flexDirection: "column", height: "100%", borderRight: "1px solid var(--border)" }}
      animate={{ width: collapsed ? 64 : 220 }}
      transition={{ duration: 0.22, ease: "easeInOut" }}
    >
      {/* Logo */}
      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", padding: "1.125rem 1rem", borderBottom: "1px solid var(--border)", flexShrink: 0 }}>
        <div style={{ width: "2rem", height: "2rem", borderRadius: "0.5rem", background: "var(--foreground)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
          <Zap style={{ width: "1rem", height: "1rem", color: "var(--background)" }} />
        </div>
        {!collapsed && (
          <motion.span
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            style={{ fontWeight: 700, color: "var(--foreground)", fontSize: "0.9375rem", letterSpacing: "0.02em" }}
          >
            ACE
          </motion.span>
        )}
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: "0.75rem 0.5rem", display: "flex", flexDirection: "column", gap: "0.125rem" }}>
        {NAV_ITEMS.map(({ href, icon: Icon, label }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={`sidebar-link ${active ? "active" : ""}`}
              style={collapsed ? { justifyContent: "center", padding: "0.625rem" } : {}}
              title={collapsed ? label : undefined}
            >
              <Icon style={{ width: "1rem", height: "1rem", flexShrink: 0 }} />
              {!collapsed && <span>{label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Voice state indicator */}
      {!collapsed && (
        <div style={{ margin: "0 0.5rem 0.5rem", padding: "0.625rem 0.75rem", background: "var(--secondary)", border: "1px solid var(--border)", borderRadius: "0.5rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <Mic style={{ width: "0.75rem", height: "0.75rem", color: stateColor, flexShrink: 0 }} />
          <span style={{ fontSize: "0.75rem", color: "var(--muted-foreground)", textTransform: "capitalize", flex: 1 }}>{pipelineState}</span>
          <motion.div
            style={{ width: "0.4rem", height: "0.4rem", borderRadius: "9999px", background: stateColor, flexShrink: 0 }}
            animate={pipelineState !== "idle" ? { scale: [1, 1.5, 1] } : {}}
            transition={{ duration: 1.2, repeat: Infinity }}
          />
        </div>
      )}

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        style={{
          margin: "0 0.5rem 0.75rem", padding: "0.5rem", borderRadius: "0.5rem", border: "1px solid var(--border)",
          background: "transparent", color: "var(--muted-foreground)", cursor: "pointer",
          display: "flex", alignItems: "center", justifyContent: "center", gap: "0.375rem",
          fontSize: "0.75rem", transition: "all 0.15s",
        }}
        onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "var(--secondary)"; (e.currentTarget as HTMLButtonElement).style.color = "var(--foreground)"; }}
        onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "transparent"; (e.currentTarget as HTMLButtonElement).style.color = "var(--muted-foreground)"; }}
      >
        {collapsed ? <ChevronRight style={{ width: "0.875rem", height: "0.875rem" }} /> : <><ChevronLeft style={{ width: "0.875rem", height: "0.875rem" }} /><span>Collapse</span></>}
      </button>
    </motion.aside>
  );
}
