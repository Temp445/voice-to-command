"use client";

import { useToastStore } from "@/store/toastStore";
import { AnimatePresence, motion } from "framer-motion";
import { X, CheckCircle, AlertCircle, Info } from "lucide-react";

export function Toaster() {
  const { toasts, dismiss } = useToastStore();

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      <AnimatePresence>
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            initial={{ opacity: 0, y: 50, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9, transition: { duration: 0.2 } }}
            className={`flex items-start gap-3 p-4 w-80 rounded-xl shadow-lg border backdrop-blur-md ${
              t.type === "success"
                ? "bg-green-500/10 border-green-500/20 text-green-500"
                : t.type === "error"
                ? "bg-red-500/10 border-red-500/20 text-red-500"
                : "bg-blue-500/10 border-blue-500/20 text-blue-500"
            }`}
          >
            <div className="flex-shrink-0 mt-0.5">
              {t.type === "success" && <CheckCircle className="w-5 h-5" />}
              {t.type === "error" && <AlertCircle className="w-5 h-5" />}
              {t.type === "info" && <Info className="w-5 h-5" />}
            </div>
            
            <div className="flex-1">
              <h3 className="font-semibold text-sm text-foreground">{t.title}</h3>
              {t.description && (
                <p className="text-sm opacity-80 mt-1">{t.description}</p>
              )}
            </div>

            <button
              onClick={() => dismiss(t.id)}
              className="flex-shrink-0 p-1 hover:bg-black/10 dark:hover:bg-white/10 rounded-full transition-colors"
            >
              <X className="w-4 h-4 text-foreground/50 hover:text-foreground" />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
