"use client";

import React, { useEffect, useState, useMemo } from "react";
import { Bell, User, ChevronDown } from "lucide-react";
import { useAuthStore } from "@/store/auth-store";
import { useTemporalStore } from "@/store/temporal-store";
import { useT } from "@/lib/i18n";
import LocaleSwitch from "./LocaleSwitch";

export default function TopBar() {
  const t = useT();
  const [clock, setClock] = useState("");
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const anomalies = useTemporalStore((s) => s.anomalies);

  const alertCount = useMemo(
    () => anomalies.filter((a) => a.severity === "HIGH" || a.severity === "CRITICAL").length,
    [anomalies]
  );

  // Tick clock every second
  useEffect(() => {
    const update = () => {
      setClock(
        new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: false,
        })
      );
    };
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <header className="topbar">
      {/* Saat — ölçülmüş değer değil, kadran bilgisi */}
      <div className="topbar-clock">{clock}</div>

      <div className="flex-1" />

      {/* Dil anahtarı — seçim tüm arayüzde geçerli, localStorage'da kalıcı */}
      <LocaleSwitch />

      {/* Uyarı — kırmızı YALNIZ gerçek tehlike sayısı varken */}
      <button
        className="topbar-btn"
        aria-label={
          alertCount > 0
            ? `${alertCount} ${t("kritik uyarı")}`
            : t("Uyarı yok")
        }
      >
        <Bell
          className="size-4"
          style={alertCount > 0 ? { color: "var(--state-critical)" } : undefined}
        />
        {alertCount > 0 && (
          <span className="topbar-badge">
            {alertCount > 9 ? "9+" : alertCount}
          </span>
        )}
      </button>

      {/* User menu */}
      <div className="relative">
        <button
          onClick={() => setUserMenuOpen((v) => !v)}
          className="topbar-user"
          aria-expanded={userMenuOpen}
        >
          <span className="rail-avatar !size-6">
            <User className="size-3.5" strokeWidth={1.7} />
          </span>
          <span className="max-w-[13rem] truncate">
            {user?.username ?? t("operatör")}
          </span>
          <ChevronDown className="size-3 text-[var(--ink-faint)]" />
        </button>

        {userMenuOpen && (
          <>
            <div
              className="fixed inset-0 z-10"
              onClick={() => setUserMenuOpen(false)}
            />
            <div className="auth-step absolute right-0 top-full z-20 mt-[var(--p-space-2)] w-56 overflow-hidden rounded-[var(--p-radius-plate)] border border-[var(--edge-hair)] bg-[color-mix(in_oklch,var(--p-graphite-990)_94%,transparent)] shadow-[var(--plate-shadow-hover)]">
              <div className="border-b border-[var(--edge-hair)] px-[var(--p-space-3)] py-[var(--p-space-3)]">
                <p className="truncate text-[var(--p-text-xs)] text-[var(--ink-title)]">
                  {user?.username ?? t("operatör")}
                </p>
                <p className="t-dial mt-[2px]">{user?.role ?? "operator"}</p>
              </div>
              <button
                onClick={() => {
                  setUserMenuOpen(false);
                  logout();
                }}
                className="w-full px-[var(--p-space-3)] py-[var(--p-space-3)] text-left text-[var(--p-text-xs)] transition-colors hover:bg-[color-mix(in_oklch,var(--state-critical)_10%,transparent)]"
                style={{ color: "var(--state-critical)" }}
              >
                {t("Oturumu kapat")}
              </button>
            </div>
          </>
        )}
      </div>
    </header>
  );
}
