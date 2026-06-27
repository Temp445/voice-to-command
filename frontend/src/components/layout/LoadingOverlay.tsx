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
      className={`fixed inset-0 z-[9999] bg-[var(--background)] flex flex-col items-center justify-center transition-opacity duration-500 ease-out ${connected ? "opacity-0 pointer-events-none" : "opacity-100 pointer-events-auto"}`}
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

      <div className="flex flex-col items-center gap-8 py-14 px-16 backdrop-blur-xl">
        <div className="relative h-[55px] flex items-center gap-2">
          {/* Glowing orb effect behind the waves */}
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-20 h-20 bg-[var(--primary)] rounded-full blur-[30px] opacity-15" />
          
          {/* Soundwave Bars */}
          <div className="ai-wave-bar" />
          <div className="ai-wave-bar" />
          <div className="ai-wave-bar" />
          <div className="ai-wave-bar" />
          <div className="ai-wave-bar" />
        </div>
        
        <div className="text-center flex flex-col gap-2">
          <h2 className="text-xl font-semibold text-[var(--foreground)] pt-[30px] tracking-tight">
            Connecting to Server
          </h2>
        </div>
      </div>
    </div>
  );
}
