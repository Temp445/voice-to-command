"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { LayoutDashboard, Terminal, GitBranch, Activity, Settings, Mic, PanelLeftClose, PanelLeftOpen, Zap, Bot, History, User, LogOut } from "lucide-react";
import { useState } from "react";
import { useVoiceStore } from "@/store/voiceStore";
import { useAuthStore } from "@/store/authStore";

const NAV_ITEMS = [
  { href: "/",           icon: LayoutDashboard, label: "Dashboard"  },
  { href: "/chat",       icon: Bot,              label: "Chat"       },
  { href: "/console",    icon: Terminal,         label: "Console"    },
  { href: "/history",    icon: History,          label: "History"    },
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
  const { user, signOut } = useAuthStore();
  const [logoHovered, setLogoHovered] = useState(false);

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
      {/* Header / Logo */}
      <div 
        onClick={toggleCollapse}
        onMouseEnter={() => setLogoHovered(true)}
        onMouseLeave={() => setLogoHovered(false)}
        style={{ 
          display: "flex", alignItems: "center", padding: collapsed ? "1.25rem 0" : "1.25rem", 
          borderBottom: "1px solid var(--border)", flexShrink: 0, cursor: "pointer",
          justifyContent: collapsed ? "center" : "space-between"
        }}
        title={collapsed ? "Expand Sidebar" : "Collapse Sidebar"}
      >
        {collapsed ? (
           logoHovered ? (
             <PanelLeftOpen style={{ width: "1.5rem", height: "1.5rem", color: "var(--muted-foreground)" }} />
           ) : (
             <div style={{ width: "2rem", height: "2rem", borderRadius: "0.5rem", background: "var(--foreground)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
               <Zap style={{ width: "1rem", height: "1rem", color: "var(--background)" }} />
             </div>
           )
        ) : (
          <>
            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
              <div style={{ width: "2rem", height: "2rem", borderRadius: "0.5rem", background: "var(--foreground)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                <Zap style={{ width: "1rem", height: "1rem", color: "var(--background)" }} />
              </div>
              <motion.span
                initial={false} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                style={{ fontWeight: 800, color: "var(--foreground)", fontSize: "1.125rem", letterSpacing: "0.02em" }}
              >
                ACE
              </motion.span>
            </div>
            <PanelLeftClose style={{ width: "1.25rem", height: "1.25rem", color: "var(--muted-foreground)" }} />
          </>
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

      {/* Profile & Logout */}
      <div style={{ display: "flex", flexDirection: "column", padding: "0.75rem", borderTop: "1px solid var(--border)", gap: "0.25rem" }}>
        <Link
          href="/profile"
          className={`sidebar-link ${pathname === "/profile" ? "active" : ""}`}
          style={collapsed ? { justifyContent: "center", padding: "0.75rem", cursor: "pointer" } : { padding: "0.75rem 1rem", gap: "0.875rem", cursor: "pointer" }}
          title={collapsed ? "Profile" : undefined}
        >
          <User style={{ width: "1.125rem", height: "1.125rem", flexShrink: 0, color: pathname === "/profile" ? "var(--primary)" : "var(--muted-foreground)" }} />
          {!collapsed && (
            <div style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}>
              <span style={{ fontSize: "0.875rem", fontWeight: 500, color: "var(--foreground)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {user?.user_metadata?.display_name || "ACE User"}
              </span>
              <span style={{ fontSize: "0.75rem", color: "var(--muted-foreground)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {user?.email}
              </span>
            </div>
          )}
        </Link>
        
        <button
          onClick={() => signOut()}
          className="sidebar-link"
          style={{
            ...(collapsed ? { justifyContent: "center", padding: "0.75rem" } : { padding: "0.75rem 1rem", gap: "0.875rem" }),
            border: "none", background: "transparent", color: "var(--state-error)", width: "100%", cursor: "pointer", textAlign: "left"
          }}
          title={collapsed ? "Logout" : undefined}
          onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "var(--secondary)"; }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "transparent"; }}
        >
          <LogOut style={{ width: "1.125rem", height: "1.125rem", flexShrink: 0 }} />
          {!collapsed && <span style={{ fontSize: "0.9375rem", fontWeight: 500 }}>Logout</span>}
        </button>
      </div>

    </motion.aside>
  );
}
