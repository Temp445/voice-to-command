"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { LayoutDashboard, Terminal, Settings, PanelLeftClose, PanelLeftOpen, Zap, Bot, History, User, LogOut } from "lucide-react";
import { useState } from "react";
import { useVoiceStore } from "@/store/voiceStore";
import { useAuthStore } from "@/store/authStore";

const NAV_ITEMS = [
  { href: "/",           icon: LayoutDashboard, label: "Dashboard"  },
  { href: "/chat",       icon: Bot,              label: "Chat"       },
  { href: "/console",    icon: Terminal,         label: "Console"    },
  { href: "/history",    icon: History,          label: "History"    },
  { href: "/settings",   icon: Settings,         label: "Settings"   },
];

export function Sidebar() {
  const pathname = usePathname();
  const { sidebarCollapsed: collapsed, setSidebarCollapsed } = useVoiceStore();
  const { user, signOut } = useAuthStore();
  const [logoHovered, setLogoHovered] = useState(false);

  const toggleCollapse = () => {
    setSidebarCollapsed(!collapsed);
  };

  return (
    <>
      {/* Mobile Backdrop Overlay */}
      {!collapsed && (
        <div 
          onClick={toggleCollapse}
          className="fixed inset-0 bg-black/40 backdrop-blur-xs z-20 md:hidden cursor-pointer"
        />
      )}
      <motion.aside
        className={`glass-strong flex flex-col h-full border-r border-[var(--border)] fixed md:relative z-30 transition-transform duration-300 md:translate-x-0 ${
          collapsed ? "-translate-x-full" : "translate-x-0"
        }`}
        initial={false}
        style={{ width: collapsed ? 64 : 240 }}
        animate={{ width: collapsed ? 64 : 240 }}
        transition={{ duration: 0.22, ease: "easeInOut" }}
      >
      {/* Header / Logo */}
      <div 
        onMouseEnter={() => setLogoHovered(true)}
        onMouseLeave={() => setLogoHovered(false)}
        className={`flex items-center border-b border-[var(--border)] shrink-0 ${collapsed ? "py-5 px-0 justify-center cursor-pointer" : "p-5 justify-between"}`}
        title={collapsed ? "Expand Sidebar" : undefined}
        onClick={collapsed ? toggleCollapse : undefined}
      >
        {collapsed ? (
          <div className="w-8 h-8 flex items-center justify-center shrink-0">
            {logoHovered ? (
              <PanelLeftOpen className="w-6 h-6 text-zinc-500" />
            ) : (
              <div className="w-8 h-8 rounded-lg bg-[var(--foreground)] flex items-center justify-center shrink-0">
                <Zap className="w-4 h-4 text-[var(--background)]" />
              </div>
            )}
          </div>
        ) : (
          <>
            <div className="flex items-center gap-3 select-none">
              <div className="w-8 h-8 rounded-lg bg-[var(--foreground)] flex items-center justify-center shrink-0">
                <Zap className="w-4 h-4 text-[var(--background)]" />
              </div>
              <motion.span
                initial={false} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                className="font-extrabold text-[var(--foreground)] text-lg tracking-wide"
              >
                ACE
              </motion.span>
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation();
                toggleCollapse();
              }}
              className="p-1.5 rounded-lg hover:bg-[var(--secondary)] text-zinc-500 hover:text-[var(--foreground)] transition-colors border-none bg-transparent cursor-pointer flex items-center justify-center"
              title="Collapse Sidebar"
            >
              <PanelLeftClose className="w-5 h-5 shrink-0" />
            </button>
          </>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 px-3 flex flex-col gap-1">
        {NAV_ITEMS.map(({ href, icon: Icon, label }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={`sidebar-link ${active ? "active" : ""} ${collapsed ? "justify-center p-3" : "px-4 py-3 gap-3.5"}`}
              title={collapsed ? label : undefined}
            >
              <Icon className="w-4.5 h-4.5 shrink-0" />
              {!collapsed && <span className="text-[15px]">{label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Profile & Logout */}
      <div className="flex flex-col p-3 border-t border-[var(--border)] gap-1">
        <Link
          href="/profile"
          className={`sidebar-link cursor-pointer ${pathname === "/profile" ? "active" : ""} ${collapsed ? "justify-center p-3" : "px-4 py-3 gap-3.5"}`}
          title={collapsed ? "Profile" : undefined}
        >
          <User className={`w-4.5 h-4.5 shrink-0 ${pathname === "/profile" ? "text-[var(--primary)]" : "text-zinc-500"}`} />
          {!collapsed && (
            <div className="flex flex-col flex-1 overflow-hidden">
              <span className="text-sm font-medium text-[var(--foreground)] truncate">
                {user?.user_metadata?.display_name || "ACE User"}
              </span>
              <span className="text-xs text-zinc-500 truncate">
                {user?.email}
              </span>
            </div>
          )}
        </Link>
        
        <button
          onClick={() => signOut()}
          className={`sidebar-link border-none bg-transparent text-[var(--state-error)] w-full cursor-pointer text-left hover:bg-[var(--secondary)] transition-all ${collapsed ? "justify-center p-3" : "px-4 py-3 gap-3.5"}`}
          title={collapsed ? "Logout" : undefined}
        >
          <LogOut className="w-4.5 h-4.5 shrink-0" />
          {!collapsed && <span className="text-[15px] font-medium">Logout</span>}
        </button>
      </div>

    </motion.aside>
    </>
  );
}
