"use client";

import React, { useEffect, useRef, useState } from "react";
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
import { useAuthStore } from "@/store/auth-store";
import { useT } from "@/lib/i18n";

/* ────────────────────────────────────────────────────────────────────────────
   SOL RAF — gravür raf + kayan gösterge

   Renk görevleri (CLAUDE.md'nin "tek accent cyan" kuralı bilerek değiştirildi):
     cyan   → yalnız ölçülmüş değer
     amber  → durum ve AKTİF SEÇİM (aktif menü, sistem sağlığı)
     kemik  → başlık ve birincil eylem
     kırmızı→ yalnız tehlike (çıkış, kritik)

   Aktif öğeyi tek bir çubuk YUMUŞAKÇA takip eder. Her öğeye ayrı çubuk
   koymak yerine tek çubuk kayınca menü bir alet kadranı gibi okunur.
   ────────────────────────────────────────────────────────────────────────── */

const NAV_GROUPS = [
  {
    label: "Görü",
    items: [
      { href: "/dashboard/vision", label: "Kamera", icon: Eye },
      { href: "/dashboard/detection", label: "Nesne Tespiti", icon: ScanSearch },
    ],
  },
  {
    label: "Analiz",
    items: [
      { href: "/dashboard/vitals", label: "Vital Değerler", icon: Activity },
      { href: "/dashboard/chat", label: "AI Asistan", icon: MessageSquare },
    ],
  },
  {
    label: "Hesap",
    items: [{ href: "/dashboard/profile", label: "Sağlık Profilim", icon: User }],
  },
] as const;

export default function Sidebar() {
  const t = useT();
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();
  const logout = useAuthStore((s) => s.logout);
  const user = useAuthStore((s) => s.user);
  const navRef = useRef<HTMLElement>(null);
  const markerRef = useRef<HTMLSpanElement>(null);

  /* Göstergeyi aktif öğenin üstüne taşı. React state yok — doğrudan CSS
     değişkeni yazılır, böylece her rota değişiminde yeniden render olmaz. */
  useEffect(() => {
    const nav = navRef.current;
    const marker = markerRef.current;
    if (!nav || !marker) return;

    const active = nav.querySelector<HTMLElement>('[aria-current="page"]');
    if (!active) {
      marker.style.setProperty("--marker-on", "0");
      return;
    }
    marker.style.setProperty("--y", `${active.offsetTop}px`);
    marker.style.setProperty("--h", `${active.offsetHeight}px`);
    marker.style.setProperty("--marker-on", "1");
  }, [pathname, collapsed]);

  let flatIndex = 0;

  return (
    <motion.aside
      animate={{ width: collapsed ? 68 : 256 }}
      transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
      className="rail"
    >
      {/* ── Marka ─────────────────────────────────────────────────────── */}
      <div className="rail-brand">
        <span className="rail-mark">
          <Eye className="size-5" strokeWidth={1.6} />
        </span>
        <AnimatePresence>
          {!collapsed && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="min-w-0"
            >
              <p className="rail-word">
                Argus<span>Lens</span>
              </p>
              <p className="t-dial mt-[2px] truncate">{t("Biyonik lens")}</p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* ── Gezinme ───────────────────────────────────────────────────── */}
      <nav ref={navRef} className="rail-nav" aria-label={t("Konsol gezinmesi")}>
        <span ref={markerRef} className="rail-marker" aria-hidden="true" />

        {NAV_GROUPS.map((group) => (
          <div key={group.label}>
            {!collapsed && <p className="rail-group">{t(group.label)}</p>}
            {group.items.map(({ href, label, icon: Icon }) => {
              const active =
                pathname === href || pathname.startsWith(href + "/");
              const i = flatIndex++;
              return (
                <Link
                  key={href}
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className="rail-item"
                  style={{ "--i": i } as React.CSSProperties}
                  title={collapsed ? t(label) : undefined}
                >
                  <Icon strokeWidth={1.7} />
                  <AnimatePresence>
                    {!collapsed && (
                      <motion.span
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="whitespace-nowrap"
                      >
                        {t(label)}
                      </motion.span>
                    )}
                  </AnimatePresence>
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      {/* ── Alt blok ──────────────────────────────────────────────────── */}
      <div className="rail-foot">
        <div className="rail-user">
          <span className="rail-avatar">
            <User className="size-4" strokeWidth={1.7} />
            <span className="rail-avatar-dot" />
          </span>
          <AnimatePresence>
            {!collapsed && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="min-w-0 flex-1"
              >
                <p className="truncate text-[var(--p-text-xs)] text-[var(--ink-title)]">
                  {user?.username ?? t("operatör")}
                </p>
                <p className="t-dial truncate">{t("Aktif")}</p>
              </motion.div>
            )}
          </AnimatePresence>
          {!collapsed && (
            <button
              onClick={logout}
              className="topbar-btn shrink-0 hover:!text-[var(--state-critical)]"
              aria-label={t("Çıkış yap")}
            >
              <LogOut className="size-4" />
            </button>
          )}
        </div>
      </div>

      {/* ── Daraltma ──────────────────────────────────────────────────── */}
      <button
        onClick={() => setCollapsed((v) => !v)}
        className="topbar-btn absolute z-20 !size-6 border border-[var(--edge-hair)] bg-[color-mix(in_oklch,var(--p-graphite-990)_80%,transparent)]"
        style={
          collapsed
            ? { top: 68, left: "50%", transform: "translateX(-50%)" }
            : { top: 22, right: 8 }
        }
        aria-label={collapsed ? t("Rafı genişlet") : t("Rafı daralt")}
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
