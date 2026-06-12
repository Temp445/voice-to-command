"use client";

import { useWSStore } from "@/hooks/useWebSocket";
import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

export function LoadingOverlay() {
  const { connected } = useWSStore();
  const [show, setShow] = useState(true);

  useEffect(() => {
    if (connected) {
      // Small delay before unmounting for smooth transition
      const timer = setTimeout(() => setShow(false), 500);
      return () => clearTimeout(timer);
    } else {
      setShow(true);
    }
  }, [connected]);

  if (!show) return null;

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        zIndex: 9999,
        background: "var(--background)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        opacity: connected ? 0 : 1,
        transition: "opacity 0.5s ease-out",
        pointerEvents: connected ? "none" : "all",
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "1.5rem",
          padding: "3rem",
          borderRadius: "2rem",
          background: "rgba(255, 255, 255, 0.03)",
          border: "1px solid rgba(255, 255, 255, 0.05)",
          backdropFilter: "blur(20px)",
          boxShadow: "0 20px 40px rgba(0, 0, 0, 0.2)",
        }}
      >
        <div style={{ position: "relative" }}>
          {/* Glowing orb effect */}
          <div
            style={{
              position: "absolute",
              top: "50%",
              left: "50%",
              transform: "translate(-50%, -50%)",
              width: "4rem",
              height: "4rem",
              background: "var(--primary)",
              borderRadius: "50%",
              filter: "blur(20px)",
              opacity: 0.3,
            }}
          />
          <Loader2 
            size={48} 
            className="animate-spin" 
            style={{ color: "var(--primary)", position: "relative", zIndex: 1 }} 
          />
        </div>
        
        <div style={{ textAlign: "center", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          <h2 style={{ fontSize: "1.25rem", fontWeight: 600, color: "var(--foreground)", letterSpacing: "-0.01em" }}>
            Connecting to ACE Engine
          </h2>
          <p style={{ fontSize: "0.875rem", color: "var(--muted-foreground)" }}>
            Waking up AI models and establishing secure connection...
          </p>
        </div>
      </div>
    </div>
  );
}
