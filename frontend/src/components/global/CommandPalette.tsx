"use client";

import React, { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Eye,
  ScanSearch,
  Activity,
  MessageSquare,
  User,
  LayoutDashboard,
  Search,
  CornerDownLeft,
} from "lucide-react";
import { cn } from "@/lib/utils";

const COMMANDS = [
  { href: "/dashboard/vision",    label: "Komuta Merkezi",  hint: "Canlı kamera akışı",         icon: LayoutDashboard },
  { href: "/dashboard/vision",    label: "Kamera",          hint: "Canlı görüntü & simülasyon", icon: Eye             },
  { href: "/dashboard/detection", label: "Nesne Tespiti",   hint: "AI görsel analiz",           icon: ScanSearch      },
  { href: "/dashboard/vitals",    label: "Vital Değerler",  hint: "Sağlık telemetrisi",         icon: Activity        },
  { href: "/dashboard/chat",      label: "AI Asistan",      hint: "Klinik yapay zeka",          icon: MessageSquare   },
  { href: "/dashboard/profile",   label: "Sağlık Profilim", hint: "Biyometrik profil",          icon: User            },
] as const;

export default function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [...COMMANDS];
    return COMMANDS.filter(
      (c) => c.label.toLowerCase().includes(q) || c.hint.toLowerCase().includes(q)
    );
  }, [query]);

  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
    setIndex(0);
  }, []);

  const go = useCallback(
    (href: string) => {
      close();
      router.push(href);
    },
    [close, router]
  );

  // Global Cmd/Ctrl+K toggle
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [close]);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 50);
  }, [open]);

  useEffect(() => {
    setIndex(0);
  }, [query]);

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setIndex((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && filtered[index]) {
      e.preventDefault();
      go(filtered[index].href);
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[90] bg-black/60 backdrop-blur-sm"
            onClick={close}
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: -12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: -12 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            className="fixed left-1/2 top-[18%] z-[91] w-full max-w-lg -translate-x-1/2 px-4"
          >
            <div className="rounded-2xl border border-[rgba(0,212,255,0.25)] bg-[#0D1117]/95 backdrop-blur-xl shadow-[0_24px_80px_rgba(0,0,0,0.6),0_0_40px_rgba(0,212,255,0.08)] overflow-hidden">
              {/* Input */}
              <div className="flex items-center gap-3 px-4 py-3.5 border-b border-[rgba(0,212,255,0.12)]">
                <Search className="size-4 text-cyan-400 shrink-0" />
                <input
                  ref={inputRef}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={onKeyDown}
                  placeholder="Sayfa ara…"
                  className="flex-1 bg-transparent text-sm text-slate-100 placeholder-slate-500 focus:outline-none"
                />
                <kbd className="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-[10px] font-mono text-slate-400">
                  ESC
                </kbd>
              </div>

              {/* Results */}
              <div className="py-2 max-h-72 overflow-y-auto">
                {filtered.length === 0 ? (
                  <p className="px-4 py-6 text-center text-xs text-slate-500">
                    Sonuç bulunamadı
                  </p>
                ) : (
                  filtered.map((c, i) => (
                    <button
                      key={c.href}
                      onClick={() => go(c.href)}
                      onMouseEnter={() => setIndex(i)}
                      className={cn(
                        "w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors",
                        i === index
                          ? "bg-cyan-500/10 border-l-2 border-cyan-400"
                          : "border-l-2 border-transparent"
                      )}
                    >
                      <c.icon
                        className={cn(
                          "size-4 shrink-0",
                          i === index ? "text-cyan-400" : "text-slate-500"
                        )}
                      />
                      <span className="flex-1 min-w-0">
                        <span
                          className={cn(
                            "block text-sm font-semibold truncate",
                            i === index ? "text-cyan-400" : "text-slate-200"
                          )}
                        >
                          {c.label}
                        </span>
                        <span className="block text-[11px] text-slate-500 truncate">
                          {c.hint}
                        </span>
                      </span>
                      {i === index && (
                        <CornerDownLeft className="size-3.5 text-slate-500 shrink-0" />
                      )}
                    </button>
                  ))
                )}
              </div>

              {/* Footer */}
              <div className="flex items-center gap-4 px-4 py-2 border-t border-[rgba(0,212,255,0.12)] text-[10px] text-slate-500">
                <span className="flex items-center gap-1">
                  <kbd className="px-1 rounded bg-slate-800 border border-slate-700 font-mono">↑↓</kbd>
                  gezin
                </span>
                <span className="flex items-center gap-1">
                  <kbd className="px-1 rounded bg-slate-800 border border-slate-700 font-mono">↵</kbd>
                  aç
                </span>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
