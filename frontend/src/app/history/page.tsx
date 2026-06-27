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
    <div className="flex h-screen overflow-hidden bg-[var(--background)]">
      {/* --- Clear Confirmation Modal --- */}
      {showClearConfirm && (
        <div className="fixed inset-0 bg-black/50 z-[100] flex items-center justify-center backdrop-blur-[4px]">
          <motion.div 
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-[var(--card)] p-6 rounded-2xl border border-[var(--border)] w-full max-w-[400px] shadow-[0_10px_25px_-5px_rgba(0,0,0,0.5)]"
          >
            <div className="flex gap-4 mb-6">
              <div className="bg-red-500/10 text-red-500 p-3 rounded-full h-fit flex items-center justify-center">
                <AlertCircle className="w-6 h-6" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-[var(--foreground)] mb-1.5">Clear All History</h2>
                <p className="text-zinc-500 text-sm m-0 leading-relaxed">
                  Are you absolutely sure you want to delete all command history? This action cannot be undone and will permanently erase these records from the database.
                </p>
              </div>
            </div>
            <div className="flex justify-end gap-3">
              <button 
                onClick={() => setShowClearConfirm(false)}
                className="px-4 py-2 rounded-lg bg-transparent border border-[var(--border)] text-[var(--foreground)] text-sm font-medium cursor-pointer transition-all duration-150 hover:bg-[var(--secondary)] active:scale-[0.98]"
              >
                Cancel
              </button>
              <button 
                onClick={() => { setShowClearConfirm(false); confirmClearHistory(); }}
                className="px-4 py-2 rounded-lg bg-red-500 border-none text-white text-sm font-medium cursor-pointer transition-all duration-150 hover:bg-red-600 active:scale-[0.98]"
              >
                Yes, Clear History
              </button>
            </div>
          </motion.div>
        </div>
      )}

      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <TopBar />
        <main className="flex-1 flex flex-col overflow-hidden p-7 gap-4">
          
          {/* Header */}
          <div className="flex items-center justify-between shrink-0">
            <div>
              <h1 className="text-3xl font-semibold text-[var(--foreground)] tracking-tight flex items-center gap-2.5">
                <History className="w-6 h-6" /> Command History
              </h1>
              <p className="text-zinc-500 text-sm mt-1">Review your past voice and text commands</p>
            </div>
            
            <div className="flex items-center gap-4">
              <button 
                onClick={fetchHistory}
                disabled={loading}
                className={`flex items-center gap-1.5 px-4 py-1.8 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] text-sm font-medium transition-all duration-150 ${loading ? "cursor-not-allowed opacity-70" : "cursor-pointer hover:bg-[var(--secondary)] active:scale-[0.98]"}`}
                title="Refresh History"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
                Refresh
              </button>

              <select 
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                className="px-3 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] text-sm outline-none cursor-pointer"
              >
                <option value="all">All Statuses</option>
                <option value="success">Success</option>
                <option value="failed">Failed</option>
              </select>

              <select 
                value={filterDate}
                onChange={(e) => setFilterDate(e.target.value)}
                className="px-3 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] text-sm outline-none cursor-pointer"
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
                  className="flex items-center gap-1.5 px-4 py-1.8 rounded-lg border border-red-500/30 bg-red-500/10 text-red-500 text-sm font-medium cursor-pointer transition-all duration-150 hover:bg-red-500/20 active:scale-[0.98]"
                >
                  <Trash2 className="w-4 h-4" /> Clear All
                </button>
              )}
            </div>
          </div>

          {/* List Container */}
          <div className="flex-1 overflow-y-auto bg-[var(--card)] border border-[var(--border)] rounded-xl p-[1px]">
            {loading ? (
              <div className="flex flex-col items-center justify-center h-full gap-4 text-zinc-500">
                <Loader2 className="w-8 h-8 animate-spin" />
                <span>Loading history...</span>
              </div>
            ) : filteredHistory.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full gap-4 text-zinc-500">
                <AlertCircle className="w-12 h-12 opacity-50" />
                <p>No matching commands found.</p>
              </div>
            ) : (
              <div className="flex flex-col">
                {filteredHistory.map((entry, idx) => {
                  const date = new Date(entry.executed_at);
                  const isSuccess = entry.status === "success";
                  
                  return (
                    <motion.div 
                      key={entry.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.2, delay: Math.min(idx * 0.05, 0.5) }}
                      className={`px-5 py-4 flex gap-4 items-center ${idx === filteredHistory.length - 1 ? "" : "border-b border-[var(--border)]"}`}
                    >
                      {/* Left: Status & Source */}
                      <div className="flex flex-col items-center gap-2 w-16 shrink-0">
                        <div className={`px-2 py-1 rounded-full text-[11px] font-bold uppercase ${isSuccess ? "bg-green-500/10 text-green-500" : "bg-red-500/10 text-red-500"}`}>
                          {entry.status}
                        </div>
                        <span className="text-xs text-zinc-500 capitalize">
                          {entry.source}
                        </span>
                      </div>

                      {/* Main content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-baseline gap-3 mb-1">
                          <h3 className="text-base font-semibold text-[var(--foreground)] m-0 truncate">
                            "{entry.raw_text}"
                          </h3>
                          {entry.intent && (
                            <span className="text-xs px-1.5 py-0.5 bg-[var(--secondary)] text-zinc-500 rounded border border-[var(--border)]">
                              {entry.intent}
                            </span>
                          )}
                        </div>
                        
                        {entry.result && (
                          <p className="m-0 text-sm text-zinc-500 line-clamp-2">
                            {entry.result}
                          </p>
                        )}
                      </div>

                      {/* Right: Meta & Actions */}
                      <div className="flex flex-col items-end gap-2 shrink-0">
                        <div className="flex items-center gap-1.5 text-xs text-zinc-500">
                          <Calendar className="w-3.5 h-3.5" />
                          {date.toLocaleDateString()} {date.toLocaleTimeString()}
                        </div>
                        {entry.duration_ms != null && (
                          <div className="flex items-center gap-1.5 text-xs text-zinc-500">
                            <Clock className="w-3.5 h-3.5" />
                            {entry.duration_ms.toFixed(0)} ms
                          </div>
                        )}
                      </div>

                      {/* Delete Action */}
                      <button 
                        onClick={() => deleteItem(entry.id)}
                        className="ml-4 p-2 bg-transparent border-none text-zinc-500 hover:text-red-500 hover:bg-[var(--secondary)] cursor-pointer rounded-md transition-all duration-150 active:scale-[0.95]"
                        title="Delete entry"
                      >
                        <Trash2 className="w-4 h-4" />
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
