"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { GitBranch, Plus, Play, Trash2, Clock, Zap, Loader2, Pencil } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { api } from "@/lib/api";
import { WorkflowModal } from "@/components/workflows/NewWorkflowModal";
import { formatDistanceToNow } from "date-fns";

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingWorkflow, setEditingWorkflow] = useState<any>(null);
  const [runningId, setRunningId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchWorkflows = async () => {
    try {
      const data = await api.listWorkflows();
      setWorkflows(data);
    } catch (error) {
      console.error("Failed to fetch workflows:", error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkflows();
  }, []);

  const handleSave = async (data: any) => {
    if (editingWorkflow) {
      await api.updateWorkflow(editingWorkflow.id, data);
    } else {
      await api.createWorkflow(data);
    }
    await fetchWorkflows();
  };

  const handleRun = async (id: string) => {
    setRunningId(id);
    try {
      await api.runWorkflow(id);
      await fetchWorkflows(); // update run_count and lastRun
    } catch (error) {
      console.error("Failed to run workflow:", error);
    } finally {
      setRunningId(null);
    }
  };

  const handleDelete = async (id: string) => {
    setDeletingId(id);
    try {
      await api.deleteWorkflow(id);
      setWorkflows(workflows.filter(wf => wf.id !== id));
    } catch (error) {
      console.error("Failed to delete workflow:", error);
    } finally {
      setDeletingId(null);
    }
  };

  const activeCount = workflows.filter(w => w.is_active).length;
  const runsToday = workflows.reduce((acc, wf) => acc + (wf.run_count || 0), 0); // Simplified stat

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "var(--background)" }}>
      <Sidebar />
      <div style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}>
        <TopBar />
        <main style={{ flex: 1, overflowY: "auto", padding: "2.5rem" }}>
          <div style={{ width: "100%", maxWidth: "56rem", margin: "0 auto", display: "flex", flexDirection: "column", gap: "2rem" }}>

            {/* Header */}
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "1rem" }}>
              <div>
                <h1 style={{ fontSize: "1.875rem", fontWeight: 800, color: "var(--foreground)", letterSpacing: "-0.02em", margin: 0 }}>Workflows</h1>
                <p style={{ color: "var(--muted-foreground)", fontSize: "0.875rem", marginTop: "0.25rem" }}>Automate multi-step tasks with a single voice command.</p>
              </div>
              <motion.button 
                whileHover={{ scale: 1.02 }} 
                whileTap={{ scale: 0.98 }}
                onClick={() => {
                  setEditingWorkflow(null);
                  setIsModalOpen(true);
                }}
                style={{ display: "flex", alignItems: "center", gap: "0.375rem", padding: "0.5rem 1rem", borderRadius: "0.5rem", border: "1px solid var(--ring)", background: "var(--primary)", color: "var(--primary-foreground)", fontSize: "0.8125rem", fontWeight: 600, cursor: "pointer", transition: "opacity 0.15s", boxShadow: "0 2px 4px rgba(0,0,0,0.1)" }}
              >
                <Plus style={{ width: "0.875rem", height: "0.875rem" }} /> New Workflow
              </motion.button>
            </div>

            {/* Stats */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem" }}>
              {[
                { label: "Total", value: workflows.length, icon: GitBranch },
                { label: "Active", value: activeCount, icon: Zap },
                { label: "Total Runs", value: runsToday, icon: Play },
              ].map(({ label, value, icon: Icon }) => (
                <div key={label} style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: "0.75rem", padding: "1.25rem", display: "flex", alignItems: "center", gap: "1rem", boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.05)" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", width: "2.5rem", height: "2.5rem", borderRadius: "0.5rem", background: "var(--secondary)" }}>
                    <Icon style={{ width: "1rem", height: "1rem", color: "var(--foreground)" }} />
                  </div>
                  <div>
                    <p style={{ fontSize: "0.7rem", color: "var(--muted-foreground)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "0.125rem", fontWeight: 600 }}>{label}</p>
                    <p style={{ fontSize: "1.5rem", fontWeight: 700, color: "var(--foreground)", lineHeight: 1 }}>{isLoading ? "-" : value}</p>
                  </div>
                </div>
              ))}
            </div>

            {/* Workflow list */}
            <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: "1rem", overflow: "hidden", boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.05)" }}>
              <div style={{ padding: "1.25rem 1.5rem", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between", background: "rgba(255,255,255,0.02)" }}>
                <p style={{ fontSize: "1rem", fontWeight: 600, color: "var(--foreground)", margin: 0 }}>Your Workflows</p>
                <span style={{ fontSize: "0.75rem", color: "var(--muted-foreground)", fontWeight: 500 }}>{workflows.length} total</span>
              </div>
              
              {isLoading ? (
                <div style={{ padding: "4rem", display: "flex", justifyContent: "center", alignItems: "center" }}>
                  <Loader2 style={{ width: "1.5rem", height: "1.5rem", animation: "spin 1s linear infinite", color: "var(--muted-foreground)" }} />
                </div>
              ) : workflows.length === 0 ? (
                /* Empty-state hint */
                <div style={{ padding: "4rem 2rem", textAlign: "center", display: "flex", flexDirection: "column", alignItems: "center" }}>
                  <GitBranch style={{ width: "3rem", height: "3rem", color: "var(--muted-foreground)", margin: "0 auto 1rem", opacity: 0.3 }} />
                  <p style={{ fontSize: "1rem", color: "var(--foreground)", fontWeight: 600, margin: "0 0 0.5rem" }}>No workflows yet</p>
                  <p style={{ fontSize: "0.875rem", color: "var(--muted-foreground)", margin: 0 }}>
                    Click &quot;New Workflow&quot; to create your first automation.
                  </p>
                </div>
              ) : (
                workflows.map((wf, i) => (
                  <motion.div key={wf.id} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.06 }}
                    style={{ padding: "1.25rem 1.5rem", display: "flex", alignItems: "center", gap: "1.25rem", borderBottom: i < workflows.length - 1 ? "1px solid var(--border)" : "none", transition: "background 0.15s" }}
                    onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.background = "var(--secondary)"; }}
                    onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.background = "transparent"; }}
                  >
                    <div style={{ width: "2.75rem", height: "2.75rem", borderRadius: "0.5rem", background: "var(--secondary)", border: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                      <GitBranch style={{ width: "1.25rem", height: "1.25rem", color: "var(--foreground)" }} />
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap", marginBottom: "0.25rem" }}>
                        <p style={{ fontSize: "1rem", fontWeight: 600, color: "var(--foreground)", margin: 0 }}>{wf.name}</p>
                        <span style={{ fontSize: "0.7rem", padding: "0.1rem 0.5rem", borderRadius: "9999px", background: wf.is_active ? "rgba(34,197,94,0.12)" : "var(--secondary)", color: wf.is_active ? "#22c55e" : "var(--muted-foreground)", border: `1px solid ${wf.is_active ? "rgba(34,197,94,0.25)" : "var(--border)"}`, fontWeight: 600 }}>
                          {wf.is_active ? "active" : "inactive"}
                        </span>
                      </div>
                      <p style={{ fontSize: "0.8125rem", color: "var(--muted-foreground)", margin: "0 0 0.5rem" }}>
                        {wf.description || `Trigger phrase: "${wf.trigger_phrase}"`}
                      </p>
                      <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                        <span style={{ fontSize: "0.75rem", color: "var(--muted-foreground)", display: "flex", alignItems: "center", gap: "0.25rem", fontWeight: 500 }}><Zap style={{ width: "0.75rem", height: "0.75rem" }} /> {wf.steps?.length || 0} steps</span>
                        <span style={{ fontSize: "0.75rem", color: "var(--muted-foreground)", display: "flex", alignItems: "center", gap: "0.25rem", fontWeight: 500 }}>
                          <Clock style={{ width: "0.75rem", height: "0.75rem" }} /> 
                          {wf.run_count > 0 ? formatDistanceToNow(new Date(wf.updated_at), { addSuffix: true }) : "Never run"}
                        </span>
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: "0.5rem", flexShrink: 0 }}>
                      <button 
                        onClick={() => {
                          setEditingWorkflow(wf);
                          setIsModalOpen(true);
                        }}
                        title="Edit workflow"
                        style={{ width: "2.25rem", height: "2.25rem", borderRadius: "0.5rem", border: "1px solid var(--border)", background: "var(--background)", color: "var(--foreground)", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", transition: "all 0.15s", boxShadow: "0 1px 2px rgba(0,0,0,0.05)" }}
                        onMouseEnter={(e) => { e.currentTarget.style.background = "var(--secondary)"; }}
                        onMouseLeave={(e) => { e.currentTarget.style.background = "var(--background)"; }}
                      >
                        <Pencil style={{ width: "1rem", height: "1rem" }} />
                      </button>
                      <button 
                        onClick={() => handleRun(wf.id)}
                        disabled={runningId === wf.id}
                        title="Run now"
                        style={{ width: "2.25rem", height: "2.25rem", borderRadius: "0.5rem", border: "1px solid var(--border)", background: "var(--background)", color: "#22c55e", cursor: runningId === wf.id ? "default" : "pointer", opacity: runningId === wf.id ? 0.5 : 1, display: "flex", alignItems: "center", justifyContent: "center", transition: "all 0.15s", boxShadow: "0 1px 2px rgba(0,0,0,0.05)" }}
                        onMouseEnter={(e) => { if(runningId !== wf.id) e.currentTarget.style.background = "rgba(34,197,94,0.1)"; }}
                        onMouseLeave={(e) => { if(runningId !== wf.id) e.currentTarget.style.background = "var(--background)"; }}
                      >
                        {runningId === wf.id ? <Loader2 style={{ width: "1rem", height: "1rem", animation: "spin 1s linear infinite" }} /> : <Play style={{ width: "1rem", height: "1rem" }} />}
                      </button>
                      <button 
                        onClick={() => handleDelete(wf.id)}
                        disabled={deletingId === wf.id}
                        title="Delete workflow"
                        style={{ width: "2.25rem", height: "2.25rem", borderRadius: "0.5rem", border: "1px solid var(--border)", background: "var(--background)", color: "#ef4444", cursor: deletingId === wf.id ? "default" : "pointer", opacity: deletingId === wf.id ? 0.5 : 1, display: "flex", alignItems: "center", justifyContent: "center", transition: "all 0.15s", boxShadow: "0 1px 2px rgba(0,0,0,0.05)" }}
                        onMouseEnter={(e) => { if(deletingId !== wf.id) e.currentTarget.style.background = "rgba(239,68,68,0.1)"; }}
                        onMouseLeave={(e) => { if(deletingId !== wf.id) e.currentTarget.style.background = "var(--background)"; }}
                      >
                        {deletingId === wf.id ? <Loader2 style={{ width: "1rem", height: "1rem", animation: "spin 1s linear infinite" }} /> : <Trash2 style={{ width: "1rem", height: "1rem" }} />}
                      </button>
                    </div>
                  </motion.div>
                ))
              )}
            </div>

          </div>
        </main>
      </div>

      <WorkflowModal 
        isOpen={isModalOpen} 
        onClose={() => {
          setIsModalOpen(false);
          setEditingWorkflow(null);
        }}
        initialData={editingWorkflow}
        onSave={handleSave} 
      />
    </div>
  );
}
