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
  const { sidebarCollapsed: collapsed, setSidebarCollapsed } = useVoiceStore();

  const toggleCollapse = () => {
    setSidebarCollapsed(!collapsed);
  };

  return (
    <motion.aside
      className="glass-strong"
      initial={false}
      style={{ display: "flex", flexDirection: "column", height: "100%", borderRight: "1px solid var(--border)", width: collapsed ? 64 : 240 }}
      animate={{ width: collapsed ? 64 : 240 }}
      transition={{ duration: 0.22, ease: "easeInOut" }}
    >
      {/* Logo */}
      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", padding: "1.25rem", borderBottom: "1px solid var(--border)", flexShrink: 0 }}>
        <div style={{ width: "2rem", height: "2rem", borderRadius: "0.5rem", background: "var(--foreground)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
          <Zap style={{ width: "1rem", height: "1rem", color: "var(--background)" }} />
        </div>
        {!collapsed && (
          <motion.span
            initial={false} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            style={{ fontWeight: 800, color: "var(--foreground)", fontSize: "1.125rem", letterSpacing: "0.02em" }}
          >
            ACE
          </motion.span>
        )}
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: "1rem 0.75rem", display: "flex", flexDirection: "column", gap: "0.25rem" }}>
        {NAV_ITEMS.map(({ href, icon: Icon, label }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={`sidebar-link ${active ? "active" : ""}`}
              style={collapsed ? { justifyContent: "center", padding: "0.75rem" } : { padding: "0.75rem 1rem", gap: "0.875rem" }}
              title={collapsed ? label : undefined}
            >
              <Icon style={{ width: "1.125rem", height: "1.125rem", flexShrink: 0 }} />
              {!collapsed && <span style={{ fontSize: "0.9375rem" }}>{label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={toggleCollapse}
        style={{
          margin: "0 0.75rem 1rem", padding: "0.625rem", borderRadius: "0.5rem", border: "1px solid var(--border)",
          background: "transparent", color: "var(--muted-foreground)", cursor: "pointer",
          display: "flex", alignItems: "center", justifyContent: "center", gap: "0.5rem",
          fontSize: "0.8125rem", fontWeight: 500, transition: "all 0.15s",
        }}
        onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "var(--secondary)"; (e.currentTarget as HTMLButtonElement).style.color = "var(--foreground)"; }}
        onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "transparent"; (e.currentTarget as HTMLButtonElement).style.color = "var(--muted-foreground)"; }}
      >
        {collapsed ? <ChevronRight style={{ width: "1rem", height: "1rem" }} /> : <><ChevronLeft style={{ width: "1rem", height: "1rem" }} /><span>Collapse Sidebar</span></>}
      </button>
    </motion.aside>
  );
}
