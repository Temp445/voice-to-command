"use client";

import { motion } from "framer-motion";
import { CheckCircle2, XCircle, Clock, Zap, Mic } from "lucide-react";
import { useCommandStore } from "@/store/commandStore";
import { format } from "date-fns";

const STATUS_STYLE = {
  success: { icon: <CheckCircle2 className="w-3.5 h-3.5 text-green-500 shrink-0" /> },
  failed:  { icon: <XCircle      className="w-3.5 h-3.5 text-red-500 shrink-0" /> },
  pending: { icon: <Clock        className="w-3.5 h-3.5 text-amber-500 shrink-0" /> },
  running: { icon: <Zap          className="w-3.5 h-3.5 text-blue-500 shrink-0" /> },
};

export function ActivityFeed() {
  const { history } = useCommandStore();
  const recent = history.slice(0, 8);

  return (
    <div className="bg-[var(--card)] border border-[var(--border)] rounded-2xl overflow-hidden shadow-sm">
      <div className="px-5 py-4 border-b border-[var(--border)] flex items-center justify-between">
        <p className="text-[13px] font-bold text-[var(--foreground)] uppercase tracking-wider opacity-90">
          Recent Activity
        </p>
        <span className="text-xs text-zinc-400 font-medium">
          {history.length} commands
        </span>
      </div>

      {recent.length === 0 ? (
        <div className="py-12 px-5 text-center flex flex-col items-center justify-center">
          <Mic className="w-8 h-8 text-[var(--border)] mb-3" />
          <p className="text-sm text-zinc-400">
            No commands yet — say{" "}
            <span className="text-[var(--foreground)] font-mono font-medium">
              &quot;alexa&quot;
            </span>{" "}
            to start
          </p>
        </div>
      ) : (
        <div className="divide-y divide-[var(--border)]">
          {recent.map((cmd, i) => {
            const status = STATUS_STYLE[cmd.status as keyof typeof STATUS_STYLE] || STATUS_STYLE.pending;
            return (
              <motion.div
                key={cmd.id ? `${cmd.id}-${i}` : i}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.04 }}
                className="px-5 py-3 flex items-center gap-3 hover:bg-[var(--secondary)]/60 transition-colors duration-150"
              >
                <div className="shrink-0">
                  {status.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] text-[var(--foreground)] font-mono truncate">
                    {cmd.raw_text}
                  </p>
                  {cmd.result && (
                    <p className="text-[11px] text-zinc-400 truncate mt-0.5">
                      {cmd.result}
                    </p>
                  )}
                </div>
                <div className="shrink-0 text-right">
                  <p className="text-[11px] text-zinc-400 font-mono">
                    {cmd.executed_at ? format(new Date(cmd.executed_at), "HH:mm:ss") : "—"}
                  </p>
                  {cmd.duration_ms !== undefined && (
                    <p className="text-[11px] text-[var(--border)] font-mono mt-0.5">
                      {(cmd.duration_ms / 1000).toFixed(2)}s
                    </p>
                  )}
                </div>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}