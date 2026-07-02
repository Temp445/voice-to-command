"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Globe, Volume2, Monitor, Search } from "lucide-react";
import { useVoice } from "@/hooks/useVoice";
import { useSettingsStore } from "@/store/settingsStore";

function ActionIcon({ logoUrl, icon: Icon, color, label }: { logoUrl?: string; icon: any; color: string; label: string }) {
  const [error, setError] = useState(false);

  if (logoUrl && !error) {
    return (
      <img
        src={logoUrl}
        alt={label}
        onError={() => setError(true)}
        className="w-4.5 h-4.5 object-contain rounded-xs"
      />
    );
  }

  return <Icon size={16} style={{ color }} className="shrink-0" />;
}

export function QuickActions() {
  const { executeText } = useVoice();
  const { crmSites } = useSettingsStore();

  const getFaviconUrl = (url: string) => {
    try {
      const cleanUrl = url.includes("://") ? url : `https://${url}`;
      const hostname = new URL(cleanUrl).hostname;
      return `https://www.google.com/s2/favicons?sz=64&domain=${hostname}`;
    } catch (e) {
      return `https://www.google.com/s2/favicons?sz=64&domain=${url}`;
    }
  };

  const getDomainColor = (url: string) => {
    try {
      const cleanUrl = url.includes("://") ? url : `https://${url}`;
      const hostname = new URL(cleanUrl).hostname.toLowerCase();

      // Match popular websites
      if (hostname.includes("google.com")) return "#3b82f6";
      if (hostname.includes("youtube.com")) return "#ef4444";
      if (hostname.includes("github.com")) return "#a855f7";
      if (hostname.includes("facebook.com")) return "#1877f2";
      if (hostname.includes("twitter.com") || hostname.includes("x.com")) return "#38bdf8";
      if (hostname.includes("linkedin.com")) return "#0a66c2";
      if (hostname.includes("reddit.com")) return "#ff4500";
      if (hostname.includes("stackoverflow.com")) return "#f48024";
      if (hostname.includes("gmail.com")) return "#ea4335";

      // Generate a stable color based on domain name hash
      let hash = 0;
      for (let i = 0; i < hostname.length; i++) {
        hash = hostname.charCodeAt(i) + ((hash << 5) - hash);
      }

      const colors = [
        "#10b981", // Emerald
        "#3b82f6", // Blue
        "#8b5cf6", // Purple
        "#ec4899", // Pink
        "#f59e0b", // Amber
        "#06b6d4", // Cyan
        "#14b8a6", // Teal
        "#f43f5e", // Rose
      ];
      return colors[Math.abs(hash) % colors.length];
    } catch (e) {
      return "#10b981";
    }
  };

  // Get the latest website shortcuts
  const latestWebsites = [...crmSites]
    .filter((site) => site.url && site.keywords)
    .slice(-4)
    .reverse()
    .map((site) => {
      const label = site.keywords.split(",")[0].trim();
      const displayLabel = label ? label.charAt(0).toUpperCase() + label.slice(1) : "Website";
      const color = getDomainColor(site.url);
      return {
        label: displayLabel,
        cmd: `open ${site.url}`,
        icon: Globe,
        logoUrl: getFaviconUrl(site.url),
        color,
      };
    });

  // Base utility actions
  const baseActions = [
    { label: "Search", cmd: "search google", icon: Search, logoUrl: "https://www.google.com/s2/favicons?sz=64&domain=google.com", color: "#3b82f6" },
    { label: "YouTube", cmd: "open youtube.com", icon: Globe, logoUrl: "https://www.google.com/s2/favicons?sz=64&domain=youtube.com", color: "#ef4444" },
    { label: "Volume Up", cmd: "volume up", icon: Volume2, color: "#8b5cf6" },
    { label: "Screenshot", cmd: "take a screenshot", icon: Monitor, color: "#06b6d4" },
  ];

  // Merge base actions and dynamic website shortcuts
  const ACTIONS = [...baseActions, ...latestWebsites];

  return (
    <div className="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-5 shadow-sm">
      <p className="text-[13px] font-bold text-[var(--foreground)] uppercase tracking-wider opacity-90 mb-4">
        Quick Actions
      </p>

      <div className="grid grid-cols-4 gap-2.5">
        {ACTIONS.map(({ label, cmd, icon: Icon, logoUrl, color }, i) => (
          <motion.button
            key={cmd}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.04 }}
            whileHover={{
              scale: 1.03,
              y: -1,
              backgroundColor: `${color}14`,
              borderColor: `${color}40`,
            }}
            whileTap={{ scale: 0.97 }}
            onClick={() => executeText(cmd)}
            className="flex flex-col items-center gap-2 p-3 rounded-xl bg-[var(--secondary)] border border-[var(--border)] transition-all duration-200 cursor-pointer"
          >
            <div
              style={{ backgroundColor: `${color}18` }}
              className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
            >
              <ActionIcon logoUrl={logoUrl} icon={Icon} color={color} label={label} />
            </div>
            <span className="text-[11px] text-zinc-400 text-center font-medium leading-tight truncate w-full px-1">
              {label}
            </span>
          </motion.button>
        ))}
      </div>
    </div>
  );
}