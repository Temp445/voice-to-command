"use client";

import { motion } from "framer-motion";
import { CheckCircle2, XCircle, Clock, Zap, Mic } from "lucide-react";
import { useCommandStore } from "@/store/commandStore";
import { format } from "date-fns";

const STATUS_STYLE = {
  success: { icon: <CheckCircle2 style={{ width: "0.875rem", height: "0.875rem", color: "#22c55e" }} />, color: "#22c55e" },
  failed:  { icon: <XCircle      style={{ width: "0.875rem", height: "0.875rem", color: "#ef4444" }} />, color: "#ef4444" },
  pending: { icon: <Clock        style={{ width: "0.875rem", height: "0.875rem", color: "#f59e0b" }} />, color: "#f59e0b" },
  running: { icon: <Zap          style={{ width: "0.875rem", height: "0.875rem", color: "#3b82f6" }} />, color: "#3b82f6" },
};

export function ActivityFeed() {
  const { history } = useCommandStore();
  const recent = history.slice(0, 8);

  return (
    <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: "1rem", overflow: "hidden" }}>
      <div style={{ padding: "1rem 1.25rem", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <p style={{ fontSize: "0.8125rem", fontWeight: 600, color: "var(--foreground)" }}>Recent Activity</p>
        <span style={{ fontSize: "0.75rem", color: "var(--muted-foreground)" }}>{history.length} commands</span>
      </div>

      {recent.length === 0 ? (
        <div style={{ padding: "3rem 1.25rem", textAlign: "center" }}>
          <Mic style={{ width: "2rem", height: "2rem", color: "var(--border)", margin: "0 auto 0.75rem" }} />
          <p style={{ fontSize: "0.875rem", color: "var(--muted-foreground)" }}>
            No commands yet — say{" "}
            <span style={{ color: "var(--foreground)", fontFamily: "var(--font-mono)" }}>&quot;alexa&quot;</span>
            {" "}to start
          </p>
        </div>
      ) : (
        <div>
          {recent.map((cmd, i) => {
            const status = STATUS_STYLE[cmd.status as keyof typeof STATUS_STYLE] || STATUS_STYLE.pending;
            return (
              <motion.div
                key={cmd.id ? `${cmd.id}-${i}` : i}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.04 }}
                style={{
                  padding: "0.75rem 1.25rem", display: "flex", alignItems: "center", gap: "0.75rem",
                  borderBottom: i < recent.length - 1 ? "1px solid var(--border)" : "none", transition: "background 0.12s",
                }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.background = "var(--secondary)"; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.background = "transparent"; }}
              >
                <div style={{ flexShrink: 0 }}>{status.icon}</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{ fontSize: "0.8125rem", color: "var(--foreground)", fontFamily: "var(--font-mono)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {cmd.raw_text}
                  </p>
                  {cmd.result && (
                    <p style={{ fontSize: "0.7rem", color: "var(--muted-foreground)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", marginTop: "0.125rem" }}>
                      {cmd.result}
                    </p>
                  )}
                </div>
                <div style={{ flexShrink: 0, textAlign: "right" }}>
                  <p style={{ fontSize: "0.7rem", color: "var(--muted-foreground)" }}>
                    {cmd.executed_at ? format(new Date(cmd.executed_at), "HH:mm:ss") : "—"}
                  </p>
                  {cmd.duration_ms !== undefined && (
                    <p style={{ fontSize: "0.7rem", color: "var(--border)", marginTop: "0.125rem" }}>{(cmd.duration_ms / 1000).toFixed(2)}s</p>
                  )}
                </div>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}