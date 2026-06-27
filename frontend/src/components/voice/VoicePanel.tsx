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
    <div className="bg-[var(--card)] border border-[var(--border)] rounded-2xl py-8 px-6 flex flex-col items-center gap-6">
      <p className="text-[11px] font-semibold tracking-widest uppercase text-zinc-500">
        Voice Assistant
      </p>

      {/* Orb */}
      <div className="relative flex items-center justify-center w-40 h-40">
        {/* Glow ring */}
        <motion.div
          className="absolute inset-0 rounded-full"
          animate={{ boxShadow: `0 0 ${isActive ? 50 : wakeWordActive ? 30 : 20}px ${idleRing}`, scale: (isActive || wakeWordActive) ? [1, 1.05, 1] : 1 }}
          transition={{ duration: 2.5, repeat: Infinity, repeatType: "reverse" }}
        />
        {/* Blob */}
        <motion.div
          style={{ background: `radial-gradient(circle, ${idleHex}25, transparent)` }}
          className="absolute inset-4 rounded-full"
          animate={{ scale: isActive ? [0.92, 1.08, 0.92] : [1, 1.03, 1], opacity: isActive ? [0.5, 1, 0.5] : [0.15, 0.35, 0.15] }}
          transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
        />
        {/* Core button */}
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={isListening ? deactivate : activate}
          style={{
            background: isActive ? config.hex : wakeWordActive ? "rgba(34,197,94,0.12)" : "var(--secondary)",
            borderColor: isActive ? config.hex : wakeWordActive ? "rgba(34,197,94,0.4)" : "var(--border)",
            boxShadow: isActive ? `0 0 24px ${config.ring}` : wakeWordActive ? "0 0 16px rgba(34,197,94,0.15)" : "none",
          }}
          className="relative w-20 h-20 rounded-full flex items-center justify-center cursor-pointer transition-colors duration-300 border-2"
        >
          {pipelineState === "speaking"   ? <Volume2 className="w-7 h-7 text-white" />
          : (pipelineState === "listening" || pipelineState === "processing") ? <WaveformIcon color="#fff" />
          : <Mic style={{ color: isActive ? "#fff" : wakeWordActive ? "#22c55e" : "var(--muted-foreground)" }} className="w-7 h-7" />}
        </motion.button>
      </div>

      {/* State label */}
      <div className="flex items-center gap-2">
        <motion.div
          style={{ background: isActive ? config.hex : wakeWordActive ? "#22c55e" : "#6B7280" }}
          className="w-1.5 h-1.5 rounded-full"
          animate={(isActive || wakeWordActive) ? { scale: [1, 1.6, 1] } : {}}
          transition={{ duration: 1, repeat: Infinity }}
        />
        <span 
          style={{ color: isActive ? config.hex : wakeWordActive ? "#22c55e" : "#6B7280" }}
          className="text-[13px] font-medium"
        >
          {config.label}
        </span>
      </div>

      {/* Waveform bars */}
      <AnimatePresence>
        {pipelineState === "listening" && (
          <motion.div
            className="flex items-end gap-1 h-10"
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
        className={`w-full py-2.5 rounded-lg text-sm font-semibold cursor-pointer flex items-center justify-center gap-2 transition-all duration-200 hover:opacity-90 active:scale-[0.98] ${
          isListening 
            ? "bg-red-500/10 text-red-500 border border-red-500/30" 
            : "bg-[var(--primary)] text-[var(--primary-foreground)] border border-[var(--primary)]"
        }`}
      >
        {isListening
          ? <><MicOff className="w-4 h-4" /> Deactivate</>
          : <><Mic className="w-4 h-4" /> Skip Wake Word &amp; Listen</>}
      </button>

      <p className="text-xs text-zinc-500 text-center leading-relaxed">
        {wakeWordActive
          ? <>Say <span className="text-green-500 font-mono font-semibold">&quot;alexa&quot;</span> to activate instantly<br/><span className="text-[11px] opacity-70">Always listening in background</span></>
          : ""}
      </p>
    </div>
  );
}

function WaveformIcon({ color }: { color: string }) {
  return (
    <div className="flex items-end gap-[3px] h-8">
      {[3, 6, 9, 7, 4].map((h, i) => (
        <motion.div 
          key={i} 
          style={{ background: color }}
          className="w-[3px] rounded-full"
          animate={{ height: [`${h * 2}px`, `${h * 4}px`, `${h * 2}px`] }}
          transition={{ duration: 0.8, repeat: Infinity, delay: i * 0.1 }}
        />
      ))}
    </div>
  );
}