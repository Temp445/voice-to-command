"use client";

import { motion } from "framer-motion";
import { GitBranch, Plus, Play, Trash2, Clock, Zap } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";

const WORKFLOWS = [
  { id: "wf-1", name: "Morning Routine",   description: "Opens VS Code, browser, and plays ambient music", steps: 4, lastRun: "2 hours ago", active: true  },
  { id: "wf-2", name: "Work Session End",  description: "Saves all files, locks screen, and mutes volume",  steps: 3, lastRun: "Yesterday",   active: true  },
  { id: "wf-3", name: "Media Mode",        description: "Opens YouTube, sets volume to 60%, dims display",   steps: 3, lastRun: "3 days ago",   active: false },
];

export default function WorkflowsPage() {
  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "var(--background)" }}>
      <Sidebar />
      <div style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}>
        <TopBar />
        <main style={{ flex: 1, overflowY: "auto", padding: "1.75rem" }}>
          <div style={{ maxWidth: "900px", margin: "0 auto", display: "flex", flexDirection: "column", gap: "1.5rem" }}>

            {/* Header */}
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
              <div>
                <h1 style={{ fontSize: "1.875rem", fontWeight: 800, color: "var(--foreground)", letterSpacing: "-0.02em" }}>Workflows</h1>
                <p style={{ color: "var(--muted-foreground)", fontSize: "0.875rem", marginTop: "0.25rem" }}>Automate multi-step tasks with a single voice command.</p>
              </div>
              <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                style={{ display: "flex", alignItems: "center", gap: "0.375rem", padding: "0.5rem 1rem", borderRadius: "0.5rem", border: "1px solid var(--ring)", background: "var(--primary)", color: "var(--primary-foreground)", fontSize: "0.8125rem", fontWeight: 600, cursor: "pointer" }}>
                <Plus style={{ width: "0.875rem", height: "0.875rem" }} /> New Workflow
              </motion.button>
            </div>

            {/* Stats */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.75rem" }}>
              {[
                { label: "Total", value: "3", icon: GitBranch },
                { label: "Active", value: "2", icon: Zap },
                { label: "Runs Today", value: "7", icon: Play },
              ].map(({ label, value, icon: Icon }) => (
                <div key={label} className="stat-card">
                  <div className="stat-card-icon"><Icon style={{ width: "1rem", height: "1rem", color: "var(--foreground)" }} /></div>
                  <div>
                    <p style={{ fontSize: "0.7rem", color: "var(--muted-foreground)", textTransform: "uppercase", letterSpacing: "0.06em" }}>{label}</p>
                    <p style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--foreground)" }}>{value}</p>
                  </div>
                </div>
              ))}
            </div>

            {/* Workflow list */}
            <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: "0.875rem", overflow: "hidden" }}>
              <div style={{ padding: "1rem 1.25rem", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <p style={{ fontSize: "0.8125rem", fontWeight: 600, color: "var(--foreground)" }}>Your Workflows</p>
                <span style={{ fontSize: "0.75rem", color: "var(--muted-foreground)" }}>{WORKFLOWS.length} total</span>
              </div>
              {WORKFLOWS.map((wf, i) => (
                <motion.div key={wf.id} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.06 }}
                  style={{ padding: "1rem 1.25rem", display: "flex", alignItems: "center", gap: "1rem", borderBottom: i < WORKFLOWS.length - 1 ? "1px solid var(--border)" : "none", transition: "background 0.12s" }}
                  onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.background = "var(--secondary)"; }}
                  onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.background = "transparent"; }}
                >
                  <div style={{ width: "2.25rem", height: "2.25rem", borderRadius: "0.5rem", background: "var(--secondary)", border: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                    <GitBranch style={{ width: "1rem", height: "1rem", color: "var(--foreground)" }} />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
                      <p style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--foreground)" }}>{wf.name}</p>
                      <span style={{ fontSize: "0.7rem", padding: "0.1rem 0.5rem", borderRadius: "9999px", background: wf.active ? "rgba(34,197,94,0.12)" : "var(--secondary)", color: wf.active ? "#22c55e" : "var(--muted-foreground)", border: `1px solid ${wf.active ? "rgba(34,197,94,0.25)" : "var(--border)"}` }}>
                        {wf.active ? "active" : "inactive"}
                      </span>
                    </div>
                    <p style={{ fontSize: "0.75rem", color: "var(--muted-foreground)", marginTop: "0.125rem" }}>{wf.description}</p>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginTop: "0.25rem" }}>
                      <span style={{ fontSize: "0.7rem", color: "var(--muted-foreground)", display: "flex", alignItems: "center", gap: "0.2rem" }}><Zap style={{ width: "0.625rem", height: "0.625rem" }} /> {wf.steps} steps</span>
                      <span style={{ fontSize: "0.7rem", color: "var(--muted-foreground)", display: "flex", alignItems: "center", gap: "0.2rem" }}><Clock style={{ width: "0.625rem", height: "0.625rem" }} /> {wf.lastRun}</span>
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: "0.375rem" }}>
                    <button style={{ width: "2rem", height: "2rem", borderRadius: "0.375rem", border: "1px solid var(--border)", background: "var(--secondary)", color: "#22c55e", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", transition: "all 0.15s" }}>
                      <Play style={{ width: "0.75rem", height: "0.75rem" }} />
                    </button>
                    <button style={{ width: "2rem", height: "2rem", borderRadius: "0.375rem", border: "1px solid var(--border)", background: "var(--secondary)", color: "#ef4444", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", transition: "all 0.15s" }}>
                      <Trash2 style={{ width: "0.75rem", height: "0.75rem" }} />
                    </button>
                  </div>
                </motion.div>
              ))}
            </div>

            {/* Empty-state hint */}
            <div style={{ background: "var(--card)", border: "1px dashed var(--border)", borderRadius: "0.875rem", padding: "2.5rem", textAlign: "center" }}>
              <GitBranch style={{ width: "2.5rem", height: "2.5rem", color: "var(--muted-foreground)", margin: "0 auto 0.75rem", opacity: 0.4 }} />
              <p style={{ fontSize: "0.875rem", color: "var(--muted-foreground)" }}>
                Say <span style={{ color: "var(--foreground)", fontFamily: "var(--font-mono)" }}>&quot;alexa, run morning routine&quot;</span> to trigger a workflow
              </p>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
