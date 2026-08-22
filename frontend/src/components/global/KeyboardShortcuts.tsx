"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Keyboard, X } from "lucide-react";

const SHORTCUTS = [
  { keys: ["Ctrl+K"], label: "Komut paleti (sayfa ara)" },
  { keys: ["G", "H"], label: "Komuta Merkezi" },
  { keys: ["G", "K"], label: "Kamera" },
  { keys: ["G", "N"], label: "Nesne Tespiti" },
  { keys: ["G", "V"], label: "Vital Değerler" },
  { keys: ["G", "A"], label: "AI Asistan" },
  { keys: ["G", "P"], label: "Sağlık Profilim" },
  { keys: ["?"], label: "Bu yardım penceresi" },
] as const;

const NAV_MAP: Record<string, string> = {
  h: "/dashboard/vision",
  k: "/dashboard/vision",
  n: "/dashboard/detection",
  v: "/dashboard/vitals",
  a: "/dashboard/chat",
  p: "/dashboard/profile",
};

export default function KeyboardShortcuts() {
  const router = useRouter();
  const [showHelp, setShowHelp] = useState(false);
  const [pendingG, setPendingG] = useState(false);

  useEffect(() => {
    let gTimer: ReturnType<typeof setTimeout>;

    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

      const key = e.key.toLowerCase();

      if (key === "?") {
        setShowHelp((v) => !v);
        return;
      }

      if (key === "escape") {
        setShowHelp(false);
        setPendingG(false);
        return;
      }

      if (key === "g") {
        setPendingG(true);
        gTimer = setTimeout(() => setPendingG(false), 1500);
        return;
      }

      if (pendingG) {
        clearTimeout(gTimer);
        setPendingG(false);
        const dest = NAV_MAP[key];
        if (dest) router.push(dest);
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [pendingG, router]);

  return (
    <>
      {/* G pending indicator */}
      <AnimatePresence>
        {pendingG && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            className="fixed bottom-4 left-4 z-50 rounded-lg border border-cyan-500/30 bg-[#0D1117] px-3 py-1.5 text-xs font-mono text-cyan-400"
          >
            G — hedef tuşuna basın
          </motion.div>
        )}
      </AnimatePresence>

      {/* Help modal */}
      <AnimatePresence>
        {showHelp && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
              onClick={() => setShowHelp(false)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.15 }}
              className="fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2 w-full max-w-sm"
            >
              <div className="rounded-2xl border border-[#1E293B] bg-[#0D1117] p-5 shadow-2xl space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-slate-300">
                    <Keyboard className="size-4" />
                    <span className="text-sm font-medium">Klavye Kısayolları</span>
                  </div>
                  <button
                    onClick={() => setShowHelp(false)}
                    className="text-slate-600 hover:text-slate-400 transition-colors"
                  >
                    <X className="size-4" />
                  </button>
                </div>
                <div className="space-y-2">
                  {SHORTCUTS.map((s) => (
                    <div
                      key={s.keys.join("+")}
                      className="flex items-center justify-between"
                    >
                      <span className="text-xs text-slate-400">{s.label}</span>
                      <div className="flex items-center gap-1">
                        {s.keys.map((k, i) => (
                          <React.Fragment key={k}>
                            {i > 0 && (
                              <span className="text-[10px] text-slate-600">sonra</span>
                            )}
                            <kbd className="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-[10px] font-mono text-slate-300">
                              {k}
                            </kbd>
                          </React.Fragment>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
