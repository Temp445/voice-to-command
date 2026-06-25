"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Terminal, Trash2, CheckCircle2, XCircle, Loader2, Mic } from "lucide-react";
import { api } from "@/lib/api";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { useVoice } from "@/hooks/useVoice";
import { useCommandStore, CommandEntry } from "@/store/commandStore";
import { useWebSocket, useWSStore } from "@/hooks/useWebSocket";
import { useSettingsStore } from "@/store/settingsStore";
import { format } from "date-fns";

export default function ConsolePage() {
  const [input, setInput] = useState("");
  const [mounted, setMounted] = useState(false);
  const { executeText } = useVoice();
  const { history, clear } = useCommandStore();
  const endRef = useRef<HTMLDivElement>(null);
  useWebSocket();
  const { connected } = useWSStore();
  const { wakeWord } = useSettingsStore();

  useEffect(() => { 
    setMounted(true);
    endRef.current?.scrollIntoView({ behavior: "smooth" }); 
  }, [history]);

  // Sync with backend database on mount
  useEffect(() => {
    api.getHistory(50).then((data: any) => {
      if (data && Array.isArray(data)) {
        useCommandStore.setState({ history: data });
      }
    }).catch(console.error);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    const text = input.trim(); setInput("");
    await executeText(text);
  };

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "var(--background)" }}>
      <Sidebar />
      <div style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}>
        <TopBar />
        <main style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", padding: "1.75rem", gap: "1rem" }}>

          {/* Header */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }}>
            <div>
              <h1 style={{ fontSize: "1.75rem", fontWeight: 600, color: "var(--foreground)", letterSpacing: "-0.02em", display: "flex", alignItems: "center", gap: "0.625rem" }}>
                <Terminal style={{ width: "1.5rem", height: "1.5rem" }} /> Command Console
              </h1>
              <p style={{ color: "var(--muted-foreground)", fontSize: "0.875rem", marginTop: "0.25rem" }}>Type commands to control your desktop</p>
            </div>
            <button onClick={async () => { clear(); await api.clearHistory(); }}
              style={{ display: "flex", alignItems: "center", gap: "0.375rem", padding: "0.4rem 0.875rem", borderRadius: "0.5rem", border: "1px solid var(--border)", background: "var(--secondary)", color: "var(--muted-foreground)", fontSize: "0.8125rem", cursor: "pointer", transition: "all 0.15s" }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.color = "#ef4444"; (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(239,68,68,0.3)"; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.color = "var(--muted-foreground)"; (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--border)"; }}
            >
              <Trash2 style={{ width: "0.875rem", height: "0.875rem" }} /> Clear
            </button>
          </div>

          {/* Terminal window */}
          <div style={{ flex: 1, display: "flex", flexDirection: "column", background: "var(--card)", border: "1px solid var(--border)", borderRadius: "0.875rem", overflow: "hidden" }}>

            {/* macOS titlebar */}
            <div style={{ padding: "0.625rem 1rem", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: "0.4rem", flexShrink: 0 }}>
              <div style={{ width: "0.625rem", height: "0.625rem", borderRadius: "9999px", background: "#ef4444" }} />
              <div style={{ width: "0.625rem", height: "0.625rem", borderRadius: "9999px", background: "#f59e0b" }} />
              <div style={{ width: "0.625rem", height: "0.625rem", borderRadius: "9999px", background: "#22c55e" }} />
              <span style={{ marginLeft: "0.5rem", fontSize: "0.75rem", color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>ace-console</span>
              <span style={{ marginLeft: "auto", fontSize: "0.7rem", color: "var(--muted-foreground)" }}>{history.length} commands</span>
            </div>

            {/* Log */}
            <div style={{ flex: 1, overflowY: "auto", padding: "1rem", display: "flex", flexDirection: "column", gap: "0.625rem", fontFamily: "var(--font-mono)", fontSize: "0.8125rem" }}>
              {!mounted ? (
                <div style={{ flex: 1, display: "flex", alignItems: "center", justifyItems: "center" }} />
              ) : history.length === 0 ? (
                <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: "0.625rem", color: "var(--muted-foreground)" }}>
                  <Terminal style={{ width: "2rem", height: "2rem", opacity: 0.3 }} />
                  <p>No commands yet. Start typing below.</p>
                  <p style={{ fontSize: "0.75rem" }}>Or say <span style={{ color: "var(--foreground)" }}>&quot;{wakeWord}&quot;</span> to use voice</p>
                </div>
              ) : (
                <AnimatePresence>
                  {[...history].reverse().map((entry) => <CommandRow key={entry.id} entry={entry} />)}
                </AnimatePresence>
              )}
              <div ref={endRef} />
            </div>

            {/* Input Area */}
            <div style={{ display: "flex", flexDirection: "column", borderTop: "1px solid var(--border)", padding: "0.75rem 1rem", gap: "0.5rem", flexShrink: 0 }}>
              <form onSubmit={handleSubmit} style={{ display: "flex", gap: "0.75rem", alignItems: "center", opacity: !connected ? 0.6 : 1 }}>
                <span style={{ color: "var(--foreground)", fontWeight: 700, fontFamily: "var(--font-mono)", fontSize: "1rem", flexShrink: 0 }}>❯</span>
                <input value={input} onChange={(e) => setInput(e.target.value)}
                  disabled={!connected}
                  placeholder={connected ? "Type a command… (e.g. open notepad)" : "Server is offline..."}
                  style={{ flex: 1, background: "transparent", border: "none", outline: "none", color: "var(--foreground)", fontFamily: "var(--font-mono)", fontSize: "0.875rem", cursor: !connected ? "not-allowed" : "text" }}
                  autoFocus={connected}
                />
                <button type="submit" disabled={!input.trim() || !connected}
                  style={{ display: "flex", alignItems: "center", gap: "0.375rem", padding: "0.5rem 1rem", borderRadius: "0.5rem", border: "1px solid var(--ring)", background: (input.trim() && connected) ? "var(--primary)" : "var(--secondary)", color: (input.trim() && connected) ? "var(--primary-foreground)" : "var(--muted-foreground)", fontSize: "0.8125rem", fontWeight: 600, cursor: (input.trim() && connected) ? "pointer" : "not-allowed", opacity: (input.trim() && connected) ? 1 : 0.5, transition: "all 0.15s" }}>
                  <Send style={{ width: "0.875rem", height: "0.875rem" }} /> Run
                </button>
              </form>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

function CommandRow({ entry }: { entry: CommandEntry }) {
  return (
    <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
        <span style={{ color: "var(--foreground)", fontWeight: 700 }}>❯</span>
        <span style={{ color: "var(--foreground)" }}>{entry.raw_text}</span>
        {entry.source === "voice" && (
          <span style={{ fontSize: "0.7rem", color: "var(--muted-foreground)", display: "flex", alignItems: "center", gap: "0.2rem" }}>
            <Mic style={{ width: "0.625rem", height: "0.625rem" }} />[voice]
          </span>
        )}
      </div>
      {entry.status === "running" ? (
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", paddingLeft: "1.25rem", color: "#f59e0b" }}>
          <Loader2 style={{ width: "0.75rem", height: "0.75rem", animation: "spin 1s linear infinite" }} />
          <span style={{ fontSize: "0.75rem" }}>Processing…</span>
          <button 
            onClick={async () => {
              useCommandStore.getState().updateEntry(entry.id, { status: "failed", result: "Cancelled by user" });
              try {
                await api.deactivate();
              } catch (e) {
                console.error("Failed to cancel on backend:", e);
              }
            }}
            style={{ marginLeft: "0.5rem", padding: "0.1rem 0.4rem", fontSize: "0.7rem", background: "rgba(239, 68, 68, 0.1)", color: "#ef4444", border: "1px solid rgba(239, 68, 68, 0.3)", borderRadius: "0.25rem", cursor: "pointer", transition: "all 0.15s" }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "rgba(239, 68, 68, 0.2)"; }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "rgba(239, 68, 68, 0.1)"; }}
          >
            Cancel
          </button>
        </div>
      ) : entry.result ? (
        <div style={{ display: "flex", alignItems: "flex-start", gap: "0.5rem", paddingLeft: "1.25rem" }}>
          {entry.status === "success"
            ? <CheckCircle2 style={{ width: "0.75rem", height: "0.75rem", color: "#22c55e", marginTop: "0.1rem", flexShrink: 0 }} />
            : <XCircle      style={{ width: "0.75rem", height: "0.75rem", color: "#ef4444", marginTop: "0.1rem", flexShrink: 0 }} />
          }
          <span style={{ color: entry.status === "success" ? "#86efac" : "#fca5a5" }}>{entry.result}</span>
        </div>
      ) : null}
      {entry.intent && (
        <p style={{ paddingLeft: "1.25rem", fontSize: "0.7rem", color: "var(--muted-foreground)" }}>
          intent: {entry.intent}{entry.duration_ms ? ` · ${(entry.duration_ms / 1000).toFixed(2)}s` : ""}{entry.executed_at ? ` · ${format(new Date(entry.executed_at), "HH:mm:ss")}` : ""}{entry.routed_by_llm ? ` · 🤖 Routed by LLM` : ""}
        </p>
      )}
    </motion.div>
  );
}
