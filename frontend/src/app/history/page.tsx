"use client";

import { useEffect, useState } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { History, Trash2, Calendar, Clock, Loader2, AlertCircle, RefreshCw } from "lucide-react";
import { motion } from "framer-motion";
import { api } from "@/lib/api";

interface CommandHistoryEntry {
  id: string;
  raw_text: string;
  intent: string | null;
  status: string;
  result: string | null;
  source: string;
  executed_at: string;
  duration_ms: number | null;
}

export default function HistoryPage() {
  const [history, setHistory] = useState<CommandHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [filterDate, setFilterDate] = useState<string>("all");
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  const fetchHistory = async () => {
    setLoading(true);
    try {
      // Fetch up to 100 items for the history view
      const data = await api.getHistory(100) as CommandHistoryEntry[];
      setHistory(data);
    } catch (e) {
      console.error("Failed to fetch history:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  const deleteItem = async (id: string) => {
    try {
      await api.deleteHistoryItem(id);
      setHistory(history.filter(h => h.id !== id));
    } catch (e) {
      console.error("Failed to delete item:", e);
    }
  };

  const handleClearClick = () => {
    setShowClearConfirm(true);
  };

  const confirmClearHistory = async () => {
    try {
      await api.clearHistory();
      setHistory([]);
    } catch (e) {
      console.error("Failed to clear history:", e);
    }
  };

  const filteredHistory = history.filter(entry => {
    if (filterStatus !== "all" && entry.status !== filterStatus) return false;
    
    if (filterDate !== "all") {
      const entryDate = new Date(entry.executed_at);
      const today = new Date();
      if (filterDate === "today") {
        if (entryDate.toDateString() !== today.toDateString()) return false;
      } else if (filterDate === "yesterday") {
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);
        if (entryDate.toDateString() !== yesterday.toDateString()) return false;
      } else if (filterDate === "week") {
        const weekAgo = new Date(today);
        weekAgo.setDate(weekAgo.getDate() - 7);
        if (entryDate < weekAgo) return false;
      } else if (filterDate === "month") {
        const monthAgo = new Date(today);
        monthAgo.setMonth(monthAgo.getMonth() - 1);
        if (entryDate < monthAgo) return false;
      }
    }
    return true;
  });

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "var(--background)" }}>
      {/* --- Clear Confirmation Modal --- */}
      {showClearConfirm && (
        <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.5)", zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center", backdropFilter: "blur(4px)" }}>
          <motion.div 
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            style={{ background: "var(--card)", padding: "1.5rem", borderRadius: "1rem", border: "1px solid var(--border)", width: "100%", maxWidth: "400px", boxShadow: "0 10px 25px -5px rgba(0,0,0,0.5)" }}
          >
            <div style={{ display: "flex", gap: "1rem", marginBottom: "1.5rem" }}>
              <div style={{ background: "rgba(239, 68, 68, 0.1)", color: "#ef4444", padding: "0.75rem", borderRadius: "9999px", height: "fit-content", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <AlertCircle style={{ width: "1.5rem", height: "1.5rem" }} />
              </div>
              <div>
                <h2 style={{ fontSize: "1.125rem", fontWeight: 600, color: "var(--foreground)", margin: "0 0 0.375rem 0" }}>Clear All History</h2>
                <p style={{ color: "var(--muted-foreground)", fontSize: "0.875rem", margin: 0, lineHeight: 1.5 }}>
                  Are you absolutely sure you want to delete all command history? This action cannot be undone and will permanently erase these records from the database.
                </p>
              </div>
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem" }}>
              <button 
                onClick={() => setShowClearConfirm(false)}
                style={{ padding: "0.5rem 1rem", borderRadius: "0.5rem", background: "transparent", border: "1px solid var(--border)", color: "var(--foreground)", fontSize: "0.875rem", fontWeight: 500, cursor: "pointer", transition: "all 0.15s" }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "var(--secondary)"; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "transparent"; }}
              >
                Cancel
              </button>
              <button 
                onClick={() => { setShowClearConfirm(false); confirmClearHistory(); }}
                style={{ padding: "0.5rem 1rem", borderRadius: "0.5rem", background: "#ef4444", border: "none", color: "white", fontSize: "0.875rem", fontWeight: 500, cursor: "pointer", transition: "all 0.15s" }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "#dc2626"; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "#ef4444"; }}
              >
                Yes, Clear History
              </button>
            </div>
          </motion.div>
        </div>
      )}

      <Sidebar />
      <div style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}>
        <TopBar />
        <main style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", padding: "1.75rem", gap: "1rem" }}>
          
          {/* Header */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }}>
            <div>
              <h1 style={{ fontSize: "1.75rem", fontWeight: 600, color: "var(--foreground)", letterSpacing: "-0.02em", display: "flex", alignItems: "center", gap: "0.625rem" }}>
                <History style={{ width: "1.5rem", height: "1.5rem" }} /> Command History
              </h1>
              <p style={{ color: "var(--muted-foreground)", fontSize: "0.875rem", marginTop: "0.25rem" }}>Review your past voice and text commands</p>
            </div>
            
            <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
              <button 
                onClick={fetchHistory}
                disabled={loading}
                style={{ display: "flex", alignItems: "center", gap: "0.375rem", padding: "0.45rem 1rem", borderRadius: "0.5rem", border: "1px solid var(--border)", background: "var(--background)", color: "var(--foreground)", fontSize: "0.875rem", fontWeight: 500, cursor: loading ? "not-allowed" : "pointer", transition: "all 0.15s", opacity: loading ? 0.7 : 1 }}
                onMouseEnter={(e) => { if (!loading) (e.currentTarget as HTMLButtonElement).style.background = "var(--secondary)"; }}
                onMouseLeave={(e) => { if (!loading) (e.currentTarget as HTMLButtonElement).style.background = "var(--background)"; }}
                title="Refresh History"
              >
                <RefreshCw style={{ width: "1rem", height: "1rem", animation: loading ? "spin 1s linear infinite" : "none" }} />
                Refresh
              </button>

              <select 
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                style={{ padding: "0.4rem 0.75rem", borderRadius: "0.5rem", border: "1px solid var(--border)", background: "var(--background)", color: "var(--foreground)", fontSize: "0.875rem", outline: "none" }}
              >
                <option value="all">All Statuses</option>
                <option value="success">Success</option>
                <option value="failed">Failed</option>
              </select>

              <select 
                value={filterDate}
                onChange={(e) => setFilterDate(e.target.value)}
                style={{ padding: "0.4rem 0.75rem", borderRadius: "0.5rem", border: "1px solid var(--border)", background: "var(--background)", color: "var(--foreground)", fontSize: "0.875rem", outline: "none" }}
              >
                <option value="all">All Time</option>
                <option value="today">Today</option>
                <option value="yesterday">Yesterday</option>
                <option value="week">Past 7 Days</option>
                <option value="month">Past 30 Days</option>
              </select>

              {history.length > 0 && (
                <button 
                  onClick={handleClearClick}
                  style={{ display: "flex", alignItems: "center", gap: "0.375rem", padding: "0.45rem 1rem", borderRadius: "0.5rem", border: "1px solid rgba(239, 68, 68, 0.3)", background: "rgba(239, 68, 68, 0.1)", color: "#ef4444", fontSize: "0.875rem", fontWeight: 500, cursor: "pointer", transition: "all 0.15s" }}
                  onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "rgba(239, 68, 68, 0.2)"; }}
                  onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "rgba(239, 68, 68, 0.1)"; }}
                >
                  <Trash2 style={{ width: "1rem", height: "1rem" }} /> Clear All
                </button>
              )}
            </div>
          </div>

          {/* List Container */}
          <div style={{ flex: 1, overflowY: "auto", background: "var(--card)", border: "1px solid var(--border)", borderRadius: "0.875rem", padding: "1px" }}>
            {loading ? (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", gap: "1rem", color: "var(--muted-foreground)" }}>
                <Loader2 style={{ width: "2rem", height: "2rem", animation: "spin 1s linear infinite" }} />
                <span>Loading history...</span>
              </div>
            ) : filteredHistory.length === 0 ? (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", gap: "1rem", color: "var(--muted-foreground)" }}>
                <AlertCircle style={{ width: "3rem", height: "3rem", opacity: 0.5 }} />
                <p>No matching commands found.</p>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column" }}>
                {filteredHistory.map((entry, idx) => {
                  const date = new Date(entry.executed_at);
                  const isSuccess = entry.status === "success";
                  
                  return (
                    <motion.div 
                      key={entry.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.2, delay: Math.min(idx * 0.05, 0.5) }}
                      style={{ 
                        padding: "1rem 1.25rem", 
                        borderBottom: idx === filteredHistory.length - 1 ? "none" : "1px solid var(--border)",
                        display: "flex",
                        gap: "1rem",
                        alignItems: "center"
                      }}
                    >
                      {/* Left: Status & Source */}
                      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "0.5rem", width: "4rem", flexShrink: 0 }}>
                        <div style={{ 
                          padding: "0.25rem 0.5rem", 
                          borderRadius: "9999px", 
                          fontSize: "0.7rem", 
                          fontWeight: 700, 
                          textTransform: "uppercase",
                          background: isSuccess ? "rgba(34, 197, 94, 0.1)" : "rgba(239, 68, 68, 0.1)",
                          color: isSuccess ? "#22c55e" : "#ef4444",
                        }}>
                          {entry.status}
                        </div>
                        <span style={{ fontSize: "0.75rem", color: "var(--muted-foreground)", textTransform: "capitalize" }}>
                          {entry.source}
                        </span>
                      </div>

                      {/* Main content */}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: "flex", alignItems: "baseline", gap: "0.75rem", marginBottom: "0.25rem" }}>
                          <h3 style={{ fontSize: "1rem", fontWeight: 600, color: "var(--foreground)", margin: 0, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                            "{entry.raw_text}"
                          </h3>
                          {entry.intent && (
                            <span style={{ fontSize: "0.75rem", padding: "0.125rem 0.375rem", background: "var(--secondary)", color: "var(--muted-foreground)", borderRadius: "0.25rem", border: "1px solid var(--border)" }}>
                              {entry.intent}
                            </span>
                          )}
                        </div>
                        
                        {entry.result && (
                          <p style={{ margin: 0, fontSize: "0.875rem", color: "var(--muted-foreground)", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                            {entry.result}
                          </p>
                        )}
                      </div>

                      {/* Right: Meta & Actions */}
                      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "0.5rem", flexShrink: 0 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.375rem", fontSize: "0.75rem", color: "var(--muted-foreground)" }}>
                          <Calendar style={{ width: "0.75rem", height: "0.75rem" }} />
                          {date.toLocaleDateString()} {date.toLocaleTimeString()}
                        </div>
                        {entry.duration_ms != null && (
                          <div style={{ display: "flex", alignItems: "center", gap: "0.375rem", fontSize: "0.75rem", color: "var(--muted-foreground)" }}>
                            <Clock style={{ width: "0.75rem", height: "0.75rem" }} />
                            {entry.duration_ms.toFixed(0)} ms
                          </div>
                        )}
                      </div>

                      {/* Delete Action */}
                      <button 
                        onClick={() => deleteItem(entry.id)}
                        style={{ marginLeft: "1rem", padding: "0.5rem", background: "transparent", border: "none", color: "var(--muted-foreground)", cursor: "pointer", borderRadius: "0.375rem", transition: "all 0.15s" }}
                        onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "var(--secondary)"; (e.currentTarget as HTMLButtonElement).style.color = "#ef4444"; }}
                        onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "transparent"; (e.currentTarget as HTMLButtonElement).style.color = "var(--muted-foreground)"; }}
                        title="Delete entry"
                      >
                        <Trash2 style={{ width: "1rem", height: "1rem" }} />
                      </button>

                    </motion.div>
                  );
                })}
              </div>
            )}
          </div>

        </main>
      </div>
    </div>
  );
}
