"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Activity, CheckCircle2, XCircle, Clock, Zap, Monitor, Globe, Folder, Camera, Play } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { getResolvedBaseUrl } from "@/lib/api";

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
  const [screenshotUrl, setScreenshotUrl] = useState<string | null>(null);
  const [isCapturing, setIsCapturing] = useState(false);
  const [testResult, setTestResult] = useState<any>(null);
  const [isRunningTest, setIsRunningTest] = useState(false);

  const takeScreenshot = async () => {
    setIsCapturing(true);
    try {
      const base = await getResolvedBaseUrl();
      const response = await fetch(`${base}/automation/browser/screenshot`, {
        method: "POST"
      });
      if (response.ok) {
        const blob = await response.blob();
        setScreenshotUrl(URL.createObjectURL(blob));
      } else {
        console.error("Failed to take screenshot");
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsCapturing(false);
    }
  };

  const runTest = async () => {
    setIsRunningTest(true);
    setTestResult(null);
    try {
      const base = await getResolvedBaseUrl();
      const response = await fetch(`${base}/automation/browser/test`, {
        method: "POST"
      });
      if (response.ok) {
        const data = await response.json();
        setTestResult(data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsRunningTest(false);
    }
  };

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "var(--background)" }}>
      <Sidebar />
      <div style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}>
        <TopBar />
        <main style={{ flex: 1, overflowY: "auto", padding: "1.75rem" }}>
          <div style={{ maxWidth: "1200px", margin: "0 auto", display: "grid", gridTemplateColumns: "1fr 350px", gap: "1.5rem" }}>
            
            <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
              {/* Header */}
              <div>
                <h1 style={{ fontSize: "1.875rem", fontWeight: 800, color: "var(--foreground)", letterSpacing: "-0.02em" }}>Automation Engine</h1>
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
                  <div key={label} className="stat-card" style={{ padding: "1rem", borderRadius: "0.75rem", background: "var(--card)", border: "1px solid var(--border)", display: "flex", alignItems: "center", gap: "1rem" }}>
                    <div className="stat-card-icon" style={{ background: "var(--secondary)", padding: "0.5rem", borderRadius: "0.5rem" }}><Icon style={{ width: "1rem", height: "1rem", color: "var(--foreground)" }} /></div>
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
            </div>

            {/* Right Column: Interactive Browser Tools */}
            <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
              
              <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: "0.875rem", padding: "1.25rem" }}>
                 <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                    <p style={{ fontSize: "0.8125rem", fontWeight: 600, color: "var(--foreground)" }}>Browser Live View</p>
                    <button 
                      onClick={takeScreenshot}
                      disabled={isCapturing}
                      style={{ background: "var(--primary)", color: "var(--primary-foreground)", border: "none", padding: "0.4rem 0.75rem", borderRadius: "0.5rem", fontSize: "0.75rem", display: "flex", alignItems: "center", gap: "0.4rem", cursor: isCapturing ? "not-allowed" : "pointer", opacity: isCapturing ? 0.7 : 1 }}
                    >
                      <Camera size={14} />
                      {isCapturing ? "Capturing..." : "Screenshot"}
                    </button>
                 </div>
                 
                 <div style={{ width: "100%", aspectRatio: "16/9", background: "var(--secondary)", borderRadius: "0.5rem", border: "1px solid var(--border)", overflow: "hidden", display: "flex", alignItems: "center", justifyContent: "center" }}>
                   {screenshotUrl ? (
                     <img src={screenshotUrl} alt="Browser Screenshot" style={{ width: "100%", height: "100%", objectFit: "contain" }} />
                   ) : (
                     <span style={{ color: "var(--muted-foreground)", fontSize: "0.75rem" }}>No screenshot available</span>
                   )}
                 </div>
              </div>

              <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: "0.875rem", padding: "1.25rem" }}>
                 <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                    <p style={{ fontSize: "0.8125rem", fontWeight: 600, color: "var(--foreground)" }}>Automated Testing</p>
                    <button 
                      onClick={runTest}
                      disabled={isRunningTest}
                      style={{ background: "var(--secondary)", color: "var(--foreground)", border: "1px solid var(--border)", padding: "0.4rem 0.75rem", borderRadius: "0.5rem", fontSize: "0.75rem", display: "flex", alignItems: "center", gap: "0.4rem", cursor: isRunningTest ? "not-allowed" : "pointer" }}
                    >
                      <Play size={14} />
                      {isRunningTest ? "Running..." : "Run Test Suite"}
                    </button>
                 </div>
                 
                 {testResult && (
                   <div style={{ marginTop: "1rem" }}>
                     <p style={{ fontSize: "0.8rem", fontWeight: 500 }}>{testResult.name}</p>
                     <p style={{ fontSize: "0.75rem", color: testResult.status === "passed" ? "#22c55e" : "#ef4444", marginBottom: "0.5rem" }}>Status: {testResult.status}</p>
                     <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
                       {testResult.steps.map((step: any, idx: number) => (
                         <div key={idx} style={{ padding: "0.5rem", background: "var(--secondary)", borderRadius: "0.25rem", fontSize: "0.75rem" }}>
                           <span style={{ color: step.status === "passed" ? "#22c55e" : "#ef4444", marginRight: "0.5rem" }}>
                             {step.status === "passed" ? "✓" : "✗"}
                           </span>
                           {step.action} {step.message && ` - ${step.message}`}
                         </div>
                       ))}
                     </div>
                   </div>
                 )}
              </div>

            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
