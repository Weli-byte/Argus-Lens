"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Eye,
  ScanSearch,
  Activity,
  MessageSquare,
  User,
  ChevronLeft,
  ChevronRight,
  LogOut,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/store/auth-store";
import { useSystemHealth } from "@/hooks/useSystemHealth";

const NAV_ITEMS = [
  { href: "/dashboard/vision",    label: "Kamera",          icon: Eye            },
  { href: "/dashboard/detection", label: "Nesne Tespiti",   icon: ScanSearch     },
  { href: "/dashboard/vitals",    label: "Vital Değerler",  icon: Activity       },
  { href: "/dashboard/chat",      label: "AI Asistan",      icon: MessageSquare  },
  { href: "/dashboard/profile",   label: "Sağlık Profilim", icon: User           },
] as const;

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();
  const logout = useAuthStore((s) => s.logout);
  const user = useAuthStore((s) => s.user);
  const { health } = useSystemHealth();

  const score = health?.score ?? null;
  const scoreColor =
    score === null
      ? "text-slate-500"
      : score >= 80
        ? "text-cyan-400"
        : score >= 60
          ? "text-amber-400"
          : "text-red-400";
  const scoreBarColor =
    score === null
      ? "bg-slate-700"
      : score >= 80
        ? "bg-cyan-400"
        : score >= 60
          ? "bg-amber-500"
          : "bg-red-500";

  return (
    <motion.aside
      animate={{ width: collapsed ? 64 : 256 }}
      transition={{ duration: 0.25, ease: "easeInOut" }}
      className="relative flex flex-col h-full bg-[#080B0F] border-r border-[rgba(0,212,255,0.12)] overflow-hidden shrink-0"
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-5 border-b border-[rgba(0,212,255,0.2)]">
        <div className="relative shrink-0 size-12 flex items-center justify-center">
          <span className="absolute inset-0 rounded-full border border-dashed border-cyan-500/30 animate-[spin_14s_linear_infinite]" />
          <span className="absolute inset-0 rounded-full bg-cyan-500/10 animate-[ring-pulse_2.6s_ease-out_infinite]" />
          <div className="relative size-10 rounded-xl bg-gradient-to-br from-cyan-500/20 to-cyan-500/5 border border-cyan-500/40 flex items-center justify-center shadow-[0_0_24px_rgba(0,212,255,0.25)]">
            <Eye className="size-7 text-cyan-400" strokeWidth={1.75} />
          </div>
        </div>
        <AnimatePresence>
          {!collapsed && (
            <motion.div
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -8 }}
              transition={{ duration: 0.15 }}
              className="min-w-0"
            >
              <p className="text-[1.4rem] leading-tight font-extrabold tracking-tight text-slate-50 whitespace-nowrap">
                Argus<span className="text-cyan-400">Lens</span>
              </p>
              <p className="text-xs text-slate-400 whitespace-nowrap">
                Biyonik Lens AI Platform
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 space-y-1 overflow-y-auto overflow-x-hidden pr-2">
        {NAV_ITEMS.map(({ href, label, icon: Icon }, navIndex) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <motion.div
              key={href}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.4, delay: navIndex * 0.1, ease: "easeOut" }}
            >
            <Link
              href={href}
              className={cn(
                "relative flex items-center gap-3 py-3 px-4 rounded-r-xl transition-all duration-300 group",
                active
                  ? "bg-[rgba(0,212,255,0.08)] text-cyan-400"
                  : "text-slate-500 hover:text-slate-200 hover:bg-[rgba(0,212,255,0.05)] hover:translate-x-1"
              )}
            >
              {active && (
                <motion.div
                  layoutId="active-pill"
                  className="absolute left-0 top-1.5 bottom-1.5 w-[3px] bg-cyan-400 rounded-r shadow-[0_0_8px_rgba(0,212,255,0.6)]"
                />
              )}
              <Icon
                className={cn(
                  "size-[18px] shrink-0 transition-colors duration-300",
                  active ? "text-cyan-400" : "text-slate-500 group-hover:text-slate-200"
                )}
                strokeWidth={active ? 2.25 : 2}
              />
              <AnimatePresence>
                {!collapsed && (
                  <motion.span
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.12 }}
                    className="text-sm font-semibold whitespace-nowrap"
                  >
                    {label}
                  </motion.span>
                )}
              </AnimatePresence>
            </Link>
            </motion.div>
          );
        })}
      </nav>

      {/* Bottom: system status + user card */}
      <div className="border-t border-[rgba(0,212,255,0.12)] p-3 space-y-3">
        {/* System status */}
        <div
          className={cn(
            "rounded-xl border border-[rgba(0,212,255,0.12)] bg-[#0D1117] px-3 py-2.5",
            collapsed && "px-2"
          )}
        >
          <div className="flex items-center justify-between gap-2">
            <AnimatePresence>
              {!collapsed && (
                <motion.span
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="text-[10px] font-semibold uppercase tracking-widest text-slate-500 whitespace-nowrap"
                >
                  Sistem
                </motion.span>
              )}
            </AnimatePresence>
            <span className={cn("text-[10px] font-mono font-bold", scoreColor)}>
              {score !== null ? `%${Math.round(score)}` : "—"}
            </span>
          </div>
          <div className="mt-1.5 h-1 rounded-full bg-slate-800 overflow-hidden">
            <div
              className={cn("h-full rounded-full transition-all duration-500", scoreBarColor)}
              style={{ width: `${score ?? 0}%` }}
            />
          </div>
        </div>

        {/* User card */}
        <div
          className={cn(
            "flex items-center gap-3 rounded-xl border border-[rgba(0,212,255,0.12)] bg-gradient-to-br from-[#0D1117] to-[#111827] p-3 transition-colors duration-300 hover:border-[rgba(0,212,255,0.3)]",
            collapsed && "justify-center p-2"
          )}
        >
          <div className="relative shrink-0">
            <div className="size-9 rounded-full bg-cyan-500/15 border border-cyan-500/40 flex items-center justify-center">
              <User className="size-4 text-cyan-400" />
            </div>
            <span className="absolute -bottom-0.5 -right-0.5 size-2.5 rounded-full bg-cyan-400 border-2 border-[#0D1117]" />
          </div>
          <AnimatePresence>
            {!collapsed && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="min-w-0 flex-1"
              >
                <p className="text-xs font-bold text-slate-100 truncate">
                  {user?.username ?? "admin"}
                </p>
                <p className="text-[10px] text-slate-500 flex items-center gap-1">
                  <span className="size-1.5 rounded-full bg-cyan-400 animate-pulse" />
                  Aktif Kullanıcı
                </p>
              </motion.div>
            )}
          </AnimatePresence>
          {!collapsed && (
            <button
              onClick={logout}
              className="shrink-0 p-1.5 rounded-lg text-slate-600 hover:text-red-400 hover:bg-red-500/10 transition-colors duration-300"
              aria-label="Çıkış Yap"
            >
              <LogOut className="size-4" />
            </button>
          )}
        </div>
      </div>

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed((v) => !v)}
        className={cn(
          "absolute size-6 rounded-full bg-[#111827]/80 border border-[rgba(0,212,255,0.25)] flex items-center justify-center text-cyan-400 hover:bg-[#161D2D] hover:shadow-[0_0_12px_rgba(0,212,255,0.3)] transition-all z-20",
          collapsed ? "top-[64px] left-1/2 -translate-x-1/2" : "top-7 right-2"
        )}
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {collapsed ? (
          <ChevronRight className="size-3" />
        ) : (
          <ChevronLeft className="size-3" />
        )}
      </button>
    </motion.aside>
  );
}
