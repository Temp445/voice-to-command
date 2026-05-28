"use client";

import { motion } from "framer-motion";
import { Activity, CheckCircle2, XCircle, Clock, Zap, Monitor, Globe, Folder } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";

const LOG = [
  { id: "a1", action: "Open VS Code",        type: "app",     status: "success", time: "10:42:05", duration: 320  },
  { id: "a2", action: "Navigate to YouTube", type: "browser", status: "success", time: "10:40:12", duration: 510  },
  { id: "a3", action: "Open Downloads",      type: "folder",  status: "success", time: "10:38:44", duration: 145  },
  { id: "a4", action: "Take Screenshot",     type: "system",  status: "failed",  time: "10:30:01", duration: 89   },
  { id: "a5", action: "Lock Screen",         type: "system",  status: "success", time: "09:55:33", duration: 210  },
  { id: "a6", action: "Volume Up",           type: "system",  status: "success", time: "09:50:22", duration: 55   },
];

const TYPE_ICON: Record<string, React.ReactNode> = {
  app:     <Monitor style={{ width: "1rem", height: "1rem", color: "var(--foreground)" }} />,
  browser: <Globe   style={{ width: "1rem", height: "1rem", color: "var(--foreground)" }} />,
  folder:  <Folder  style={{ width: "1rem", height: "1rem", color: "var(--foreground)" }} />,
  system:  <Zap     style={{ width: "1rem", height: "1rem", color: "var(--foreground)" }} />,
};

const TYPE_LABEL: Record<string, string> = { app: "Desktop", browser: "Browser", folder: "File System", system: "System" };

export default function AutomationPage() {
  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "var(--background)" }}>
      <Sidebar />
      <div style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}>
        <TopBar />
        <main style={{ flex: 1, overflowY: "auto", padding: "1.75rem" }}>
          <div style={{ maxWidth: "900px", margin: "0 auto", display: "flex", flexDirection: "column", gap: "1.5rem" }}>

            {/* Header */}
            <div>
              <h1 style={{ fontSize: "1.875rem", fontWeight: 800, color: "var(--foreground)", letterSpacing: "-0.02em" }}>Automation</h1>
              <p style={{ color: "var(--muted-foreground)", fontSize: "0.875rem", marginTop: "0.25rem" }}>Live automation engine status and execution logs.</p>
            </div>

            {/* Engine status */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "0.75rem" }}>
              {[
                { label: "Desktop Engine", value: "Ready", icon: Monitor },
                { label: "Browser Engine", value: "Ready", icon: Globe   },
                { label: "System Engine",  value: "Ready", icon: Zap     },
                { label: "Total Actions",  value: `${LOG.length}`, icon: Activity },
              ].map(({ label, value, icon: Icon }) => (
                <div key={label} className="stat-card">
                  <div className="stat-card-icon"><Icon style={{ width: "1rem", height: "1rem", color: "var(--foreground)" }} /></div>
                  <div style={{ minWidth: 0 }}>
                    <p style={{ fontSize: "0.7rem", color: "var(--muted-foreground)", textTransform: "uppercase", letterSpacing: "0.06em", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{label}</p>
                    <p style={{ fontSize: "0.875rem", fontWeight: 600, color: value === "Ready" ? "#22c55e" : "var(--foreground)" }}>{value}</p>
                  </div>
                </div>
              ))}
            </div>

            {/* Log table */}
            <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: "0.875rem", overflow: "hidden" }}>
              <div style={{ padding: "1rem 1.25rem", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <p style={{ fontSize: "0.8125rem", fontWeight: 600, color: "var(--foreground)" }}>Execution Log</p>
                <span style={{ fontSize: "0.75rem", color: "var(--muted-foreground)" }}>{LOG.length} entries</span>
              </div>
              {LOG.map((log, i) => (
                <motion.div key={log.id} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}
                  style={{ padding: "0.875rem 1.25rem", display: "flex", alignItems: "center", gap: "0.875rem", borderBottom: i < LOG.length - 1 ? "1px solid var(--border)" : "none", transition: "background 0.12s" }}
                  onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.background = "var(--secondary)"; }}
                  onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.background = "transparent"; }}
                >
                  <div style={{ width: "2rem", height: "2rem", borderRadius: "0.375rem", background: "var(--secondary)", border: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                    {TYPE_ICON[log.type]}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p style={{ fontSize: "0.8125rem", fontWeight: 500, color: "var(--foreground)", fontFamily: "var(--font-mono)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{log.action}</p>
                    <p style={{ fontSize: "0.7rem", color: "var(--muted-foreground)", marginTop: "0.125rem" }}>{TYPE_LABEL[log.type]} automation</p>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.375rem", flexShrink: 0 }}>
                    {log.status === "success"
                      ? <CheckCircle2 style={{ width: "0.875rem", height: "0.875rem", color: "#22c55e" }} />
                      : <XCircle      style={{ width: "0.875rem", height: "0.875rem", color: "#ef4444" }} />
                    }
                    <span style={{ fontSize: "0.75rem", fontWeight: 500, color: log.status === "success" ? "#22c55e" : "#ef4444", textTransform: "capitalize" }}>{log.status}</span>
                  </div>
                  <div style={{ flexShrink: 0, textAlign: "right" }}>
                    <p style={{ fontSize: "0.7rem", color: "var(--muted-foreground)", display: "flex", alignItems: "center", gap: "0.2rem", justifyContent: "flex-end" }}>
                      <Clock style={{ width: "0.625rem", height: "0.625rem" }} />{log.time}
                    </p>
                    <p style={{ fontSize: "0.7rem", color: "var(--muted-foreground)", marginTop: "0.125rem" }}>{log.duration}ms</p>
                  </div>
                </motion.div>
              ))}
            </div>

            {/* Supported types */}
            <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: "0.875rem", padding: "1.25rem" }}>
              <p style={{ fontSize: "0.8125rem", fontWeight: 600, color: "var(--foreground)", marginBottom: "0.875rem" }}>Supported Automation Types</p>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "0.75rem" }}>
                {[
                  { label: "App Launch",   desc: "pywinauto",  icon: Monitor },
                  { label: "Browser",      desc: "Playwright", icon: Globe   },
                  { label: "File System",  desc: "os / pathlib",icon: Folder },
                  { label: "System Tasks", desc: "pynput",     icon: Zap     },
                ].map(({ label, desc, icon: Icon }) => (
                  <div key={label} style={{ padding: "0.875rem", borderRadius: "0.5rem", background: "var(--secondary)", border: "1px solid var(--border)", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                    <div style={{ width: "2rem", height: "2rem", borderRadius: "0.375rem", background: "var(--muted)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                      <Icon style={{ width: "1rem", height: "1rem", color: "var(--foreground)" }} />
                    </div>
                    <p style={{ fontSize: "0.8125rem", fontWeight: 600, color: "var(--foreground)" }}>{label}</p>
                    <p style={{ fontSize: "0.75rem", fontFamily: "var(--font-mono)", color: "var(--muted-foreground)" }}>{desc}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
