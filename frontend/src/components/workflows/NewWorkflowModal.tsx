"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Plus, Trash2, Save } from "lucide-react";

interface WorkflowModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialData?: any;
  onSave: (data: { name: string; description: string; trigger_phrase: string; steps: { action: string; delay_ms: number }[] }) => Promise<void>;
}

const inp = { width: "100%", background: "var(--input)", border: "1px solid var(--border)", borderRadius: "0.5rem", padding: "0.625rem 0.875rem", fontSize: "0.875rem", color: "var(--foreground)", outline: "none", transition: "border-color 0.2s" } as React.CSSProperties;
const lbl = { fontSize: "0.8125rem", fontWeight: 600, color: "var(--foreground)", marginBottom: "0.375rem", display: "block" } as React.CSSProperties;

export function WorkflowModal({ isOpen, onClose, initialData, onSave }: WorkflowModalProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [triggerPhrase, setTriggerPhrase] = useState("");
  const [steps, setSteps] = useState<{ action: string; delay_ms: number }[]>([{ action: "", delay_ms: 0 }]);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (isOpen && initialData) {
      setName(initialData.name || "");
      setDescription(initialData.description || "");
      setTriggerPhrase(initialData.trigger_phrase || "");
      setSteps(initialData.steps?.length > 0 ? initialData.steps : [{ action: "", delay_ms: 0 }]);
    } else if (isOpen && !initialData) {
      setName("");
      setDescription("");
      setTriggerPhrase("");
      setSteps([{ action: "", delay_ms: 0 }]);
    }
  }, [isOpen, initialData]);

  const handleAddStep = () => {
    setSteps([...steps, { action: "", delay_ms: 0 }]);
  };

  const handleRemoveStep = (index: number) => {
    setSteps(steps.filter((_, i) => i !== index));
  };

  const handleStepChange = (index: number, field: "action" | "delay_ms", value: string | number) => {
    const newSteps = [...steps];
    newSteps[index] = { ...newSteps[index], [field]: value };
    setSteps(newSteps);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !triggerPhrase || steps.some(s => !s.action)) return;
    
    setIsSaving(true);
    try {
      await onSave({ name, description, trigger_phrase: triggerPhrase, steps });
      onClose();
    } catch (err) {
      console.error(err);
    } finally {
      setIsSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div style={{ position: "fixed", inset: 0, zIndex: 50, display: "flex", alignItems: "center", justifyContent: "center", padding: "1rem", background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}>
        <motion.div 
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: "1rem", boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)", width: "100%", maxWidth: "42rem", maxHeight: "90vh", display: "flex", flexDirection: "column", overflow: "hidden" }}
        >
          {/* Header */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "1.25rem 1.5rem", borderBottom: "1px solid var(--border)", background: "rgba(255,255,255,0.02)" }}>
            <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: "var(--foreground)", margin: 0 }}>
              {initialData ? "Edit Workflow" : "Create New Workflow"}
            </h2>
            <button type="button" onClick={onClose} style={{ background: "transparent", border: "none", cursor: "pointer", padding: "0.25rem", color: "var(--muted-foreground)", display: "flex", alignItems: "center", justifyContent: "center", borderRadius: "0.375rem", transition: "background 0.2s" }} onMouseEnter={(e) => e.currentTarget.style.background = "var(--secondary)"} onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}>
              <X style={{ width: "1.25rem", height: "1.25rem" }} />
            </button>
          </div>

          {/* Body */}
          <div style={{ padding: "1.5rem", overflowY: "auto", flex: 1 }}>
            <form id="workflow-form" onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
              <div>
                <label style={lbl}>Workflow Name <span style={{ color: "#ef4444" }}>*</span></label>
                <input 
                  autoFocus
                  required
                  placeholder="e.g. Morning Routine"
                  value={name} onChange={(e) => setName(e.target.value)}
                  style={inp}
                  onFocus={(e) => e.currentTarget.style.borderColor = "var(--ring)"}
                  onBlur={(e) => e.currentTarget.style.borderColor = "var(--border)"}
                />
              </div>

              <div>
                <label style={lbl}>Voice Trigger Phrase <span style={{ color: "#ef4444" }}>*</span></label>
                <input 
                  required
                  placeholder="What should you say? (e.g. start my morning)"
                  value={triggerPhrase} onChange={(e) => setTriggerPhrase(e.target.value)}
                  style={inp}
                  onFocus={(e) => e.currentTarget.style.borderColor = "var(--ring)"}
                  onBlur={(e) => e.currentTarget.style.borderColor = "var(--border)"}
                />
              </div>

              <div>
                <label style={lbl}>Description</label>
                <input 
                  placeholder="Optional description"
                  value={description} onChange={(e) => setDescription(e.target.value)}
                  style={inp}
                  onFocus={(e) => e.currentTarget.style.borderColor = "var(--ring)"}
                  onBlur={(e) => e.currentTarget.style.borderColor = "var(--border)"}
                />
              </div>

              <div style={{ marginTop: "0.5rem" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.75rem" }}>
                  <label style={lbl}>Automation Steps</label>
                  <button type="button" onClick={handleAddStep} style={{ display: "flex", alignItems: "center", gap: "0.25rem", fontSize: "0.75rem", fontWeight: 600, color: "var(--primary)", background: "transparent", border: "none", cursor: "pointer" }}>
                    <Plus style={{ width: "0.875rem", height: "0.875rem" }} /> Add Step
                  </button>
                </div>
                
                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  {steps.map((step, idx) => (
                    <div key={idx} style={{ display: "flex", gap: "0.75rem", alignItems: "flex-start", background: "var(--background)", padding: "0.75rem", borderRadius: "0.5rem", border: "1px solid var(--border)", position: "relative" }}>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", width: "1.75rem", height: "2.25rem", background: "var(--secondary)", borderRadius: "0.25rem", fontSize: "0.75rem", fontWeight: 600, color: "var(--muted-foreground)" }}>
                        {idx + 1}
                      </div>
                      <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                        <input 
                          required
                          placeholder="Action (e.g. open chrome, type 'hello')"
                          value={step.action} 
                          onChange={(e) => handleStepChange(idx, "action", e.target.value)}
                          style={{ ...inp, padding: "0.5rem 0.75rem" }}
                          onFocus={(e) => e.currentTarget.style.borderColor = "var(--ring)"}
                          onBlur={(e) => e.currentTarget.style.borderColor = "var(--border)"}
                        />
                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                          <span style={{ fontSize: "0.75rem", color: "var(--muted-foreground)" }}>Delay before step (ms):</span>
                          <input 
                            type="number" min="0" step="100"
                            value={step.delay_ms} 
                            onChange={(e) => handleStepChange(idx, "delay_ms", parseInt(e.target.value) || 0)}
                            style={{ ...inp, width: "6rem", padding: "0.25rem 0.5rem", fontSize: "0.75rem" }}
                            onFocus={(e) => e.currentTarget.style.borderColor = "var(--ring)"}
                            onBlur={(e) => e.currentTarget.style.borderColor = "var(--border)"}
                          />
                        </div>
                      </div>
                      {steps.length > 1 && (
                        <button type="button" onClick={() => handleRemoveStep(idx)} style={{ padding: "0.375rem", color: "#ef4444", background: "transparent", border: "none", cursor: "pointer", borderRadius: "0.375rem", position: "absolute", right: "0.5rem", top: "0.5rem", transition: "background 0.2s" }} onMouseEnter={(e) => e.currentTarget.style.background = "rgba(239,68,68,0.1)"} onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}>
                          <Trash2 style={{ width: "1rem", height: "1rem" }} />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </form>
          </div>

          {/* Footer */}
          <div style={{ padding: "1.25rem 1.5rem", borderTop: "1px solid var(--border)", display: "flex", justifyContent: "flex-end", gap: "0.75rem", background: "var(--background)" }}>
            <button type="button" onClick={onClose} style={{ padding: "0.625rem 1rem", borderRadius: "0.5rem", fontSize: "0.8125rem", fontWeight: 600, color: "var(--foreground)", background: "transparent", border: "1px solid var(--border)", cursor: "pointer", transition: "background 0.2s" }} onMouseEnter={(e) => e.currentTarget.style.background = "var(--secondary)"} onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}>
              Cancel
            </button>
            <button 
              type="submit" form="workflow-form" disabled={isSaving}
              style={{ display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.625rem 1.25rem", borderRadius: "0.5rem", fontSize: "0.8125rem", fontWeight: 600, color: "var(--primary-foreground)", background: "var(--primary)", border: "1px solid var(--ring)", cursor: isSaving ? "default" : "pointer", opacity: isSaving ? 0.7 : 1, transition: "opacity 0.2s", boxShadow: "0 2px 4px rgba(0,0,0,0.1)" }}
            >
              {isSaving ? "Saving..." : <><Save style={{ width: "1rem", height: "1rem" }} /> {initialData ? "Update Workflow" : "Save Workflow"}</>}
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
