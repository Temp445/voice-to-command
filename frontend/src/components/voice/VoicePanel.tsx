"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Mic, MicOff, Volume2 } from "lucide-react";
import { useVoiceStore } from "@/store/voiceStore";
import { useVoice } from "@/hooks/useVoice";

const STATE_CONFIG = {
  idle:       { label: "Wake Word Active", color: "var(--state-idle)",       hex: "#6B7280", ring: "rgba(107,114,128,0.15)" },
  listening:  { label: "Listening",        color: "var(--state-listening)",  hex: "#22c55e", ring: "rgba(34,197,94,0.2)"  },
  processing: { label: "Processing",       color: "var(--state-processing)", hex: "#f59e0b", ring: "rgba(245,158,11,0.2)" },
  speaking:   { label: "Speaking",         color: "var(--state-speaking)",   hex: "#3b82f6", ring: "rgba(59,130,246,0.2)" },
  error:      { label: "Error",            color: "var(--state-error)",      hex: "#ef4444", ring: "rgba(239,68,68,0.2)"  },
};

export function VoicePanel() {
  const { pipelineState, isListening, wakeWordActive } = useVoiceStore();
  const { activate, deactivate } = useVoice();

  const config = STATE_CONFIG[pipelineState as keyof typeof STATE_CONFIG] || STATE_CONFIG.idle;
  const isActive = pipelineState !== "idle";
  // In idle state, override color to green to show always-listening wake word
  const idleHex = wakeWordActive && !isActive ? "#22c55e" : config.hex;
  const idleRing = wakeWordActive && !isActive ? "rgba(34,197,94,0.12)" : config.ring;

  return (
    <div style={{
      background: "var(--card)", border: "1px solid var(--border)", borderRadius: "1rem",
      padding: "2rem 1.5rem", display: "flex", flexDirection: "column", alignItems: "center", gap: "1.5rem",
    }}>
      <p style={{ fontSize: "0.6875rem", fontWeight: 600, letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--muted-foreground)" }}>
        Voice Assistant
      </p>

      {/* Orb */}
      <div style={{ position: "relative", display: "flex", alignItems: "center", justifyContent: "center", width: "10rem", height: "10rem" }}>
        {/* Glow ring */}
        <motion.div
          style={{ position: "absolute", inset: 0, borderRadius: "9999px" }}
          animate={{ boxShadow: `0 0 ${isActive ? 50 : wakeWordActive ? 30 : 20}px ${idleRing}`, scale: (isActive || wakeWordActive) ? [1, 1.05, 1] : 1 }}
          transition={{ duration: 2.5, repeat: Infinity, repeatType: "reverse" }}
        />
        {/* Blob */}
        <motion.div
          style={{ position: "absolute", inset: "1rem", borderRadius: "9999px", background: `radial-gradient(circle, ${idleHex}25, transparent)` }}
          animate={{ scale: isActive ? [0.92, 1.08, 0.92] : [1, 1.03, 1], opacity: isActive ? [0.5, 1, 0.5] : [0.15, 0.35, 0.15] }}
          transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
        />
        {/* Core button */}
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={isListening ? deactivate : activate}
          style={{
            position: "relative", width: "5rem", height: "5rem", borderRadius: "9999px",
            background: isActive ? config.hex : wakeWordActive ? "rgba(34,197,94,0.12)" : "var(--secondary)",
            border: `2px solid ${isActive ? config.hex : wakeWordActive ? "rgba(34,197,94,0.4)" : "var(--border)"}`,
            display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer",
            transition: "background 0.3s, border-color 0.3s",
            boxShadow: isActive ? `0 0 24px ${config.ring}` : wakeWordActive ? "0 0 16px rgba(34,197,94,0.15)" : "none",
          }}
        >
          {pipelineState === "speaking"   ? <Volume2 style={{ width: "1.75rem", height: "1.75rem", color: "#fff" }} />
          : (pipelineState === "listening" || pipelineState === "processing") ? <WaveformIcon color="#fff" />
          : <Mic style={{ width: "1.75rem", height: "1.75rem", color: isActive ? "#fff" : wakeWordActive ? "#22c55e" : "var(--muted-foreground)" }} />}
        </motion.button>
      </div>

      {/* State label */}
      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
        <motion.div
          style={{ width: "0.4rem", height: "0.4rem", borderRadius: "9999px", background: isActive ? config.hex : wakeWordActive ? "#22c55e" : "#6B7280" }}
          animate={(isActive || wakeWordActive) ? { scale: [1, 1.6, 1] } : {}}
          transition={{ duration: 1, repeat: Infinity }}
        />
        <span style={{ fontSize: "0.8125rem", fontWeight: 500, color: isActive ? config.hex : wakeWordActive ? "#22c55e" : "#6B7280" }}>
          {config.label}
        </span>
      </div>

      {/* Waveform bars */}
      <AnimatePresence>
        {pipelineState === "listening" && (
          <motion.div
            style={{ display: "flex", alignItems: "flex-end", gap: "0.25rem", height: "2.5rem" }}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          >
            {Array.from({ length: 7 }).map((_, i) => (
              <span key={i} className="wave-bar" style={{ background: config.hex }} />
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Activate / Deactivate button */}
      <button
        onClick={isListening ? deactivate : activate}
        style={{
          width: "100%", padding: "0.6875rem", borderRadius: "0.5rem", fontSize: "0.875rem", fontWeight: 600,
          cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: "0.5rem", transition: "all 0.2s",
          background: isListening ? "rgba(239,68,68,0.1)"   : "var(--primary)",
          color:      isListening ? "#ef4444"                : "var(--primary-foreground)",
          border:     isListening ? "1px solid rgba(239,68,68,0.3)" : "1px solid var(--primary)",
        }}
        onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.opacity = "0.8"; }}
        onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.opacity = "1"; }}
      >
        {isListening
          ? <><MicOff style={{ width: "1rem", height: "1rem" }} /> Deactivate</>
          : <><Mic    style={{ width: "1rem", height: "1rem" }} /> Skip Wake Word &amp; Listen</>}
      </button>

      <p style={{ fontSize: "0.75rem", color: "var(--muted-foreground)", textAlign: "center", lineHeight: 1.5 }}>
        {wakeWordActive
          ? <>Say <span style={{ color: "#22c55e", fontFamily: "var(--font-mono)", fontWeight: 600 }}>&quot;alexa&quot;</span> to activate instantly<br/><span style={{ fontSize: "0.6875rem", opacity: 0.7 }}>Always listening in background</span></>
          : ""}
      </p>
    </div>
  );
}

function WaveformIcon({ color }: { color: string }) {
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: "3px", height: "2rem" }}>
      {[3, 6, 9, 7, 4].map((h, i) => (
        <motion.div key={i} style={{ width: "3px", borderRadius: "9999px", background: color }}
          animate={{ height: [`${h * 2}px`, `${h * 4}px`, `${h * 2}px`] }}
          transition={{ duration: 0.8, repeat: Infinity, delay: i * 0.1 }}
        />
      ))}
    </div>
  );
}