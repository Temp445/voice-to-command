"use client";

import { useWSStore } from "@/hooks/useWebSocket";
import { useEffect, useState } from "react";

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
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes soundwave {
          0%, 100% { transform: scaleY(0.3); opacity: 0.5; }
          50% { transform: scaleY(1); opacity: 1; }
        }
        .ai-wave-bar {
          width: 6px;
          height: 40px;
          background: var(--primary);
          border-radius: 9999px;
          animation: soundwave 1.2s cubic-bezier(0.4, 0, 0.2, 1) infinite;
          transform-origin: center;
          box-shadow: 0 0 10px var(--primary);
        }
        .ai-wave-bar:nth-child(1) { animation-delay: 0.0s; height: 25px; }
        .ai-wave-bar:nth-child(2) { animation-delay: 0.15s; height: 40px; }
        .ai-wave-bar:nth-child(3) { animation-delay: 0.3s; height: 55px; }
        .ai-wave-bar:nth-child(4) { animation-delay: 0.45s; height: 40px; }
        .ai-wave-bar:nth-child(5) { animation-delay: 0.6s; height: 25px; }
      `}} />

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "2rem",
          padding: "3.5rem 4rem",
          // borderRadius: "2rem",
          // background: "rgba(255, 255, 255, 0.02)",
          // border: "1px solid rgba(255, 255, 255, 0.05)",
          backdropFilter: "blur(20px)",
          // boxShadow: "0 30px 60px rgba(0, 0, 0, 0.4)",
        }}
      >
        <div style={{ position: "relative", height: "55px", display: "flex", alignItems: "center", gap: "8px" }}>
          {/* Glowing orb effect behind the waves */}
          <div
            style={{
              position: "absolute",
              top: "50%",
              left: "50%",
              transform: "translate(-50%, -50%)",
              width: "5rem",
              height: "5rem",
              background: "var(--primary)",
              borderRadius: "50%",
              filter: "blur(30px)",
              opacity: 0.15,
            }}
          />
          
          {/* Soundwave Bars */}
          <div className="ai-wave-bar" />
          <div className="ai-wave-bar" />
          <div className="ai-wave-bar" />
          <div className="ai-wave-bar" />
          <div className="ai-wave-bar" />
        </div>
        
        <div style={{ textAlign: "center", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          <h2 style={{ fontSize: "1.25rem", fontWeight: 600, color: "var(--foreground)", paddingTop: 30, letterSpacing: "-0.01em" }}>
            Connecting to Server
          </h2>
        </div>
      </div>
    </div>
  );
}
