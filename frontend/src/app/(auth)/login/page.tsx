"use client";

import Link from "next/link";
import AuthAperture from "@/components/auth/AuthAperture";
import AuthPanels from "@/components/auth/AuthPanels";
import LocaleSwitch from "@/components/layout/LocaleSwitch";

/**
 * Kimlik ekranı — tam ekran video sahnesi + TEK panel.
 *
 * Önce GİRİŞ ve KAYIT ayrı iki tam ekran bölümdü (01/02); gereksiz uzundu ve
 * kullanıcıyı kaydırmaya zorluyordu. Şimdi ikisi aynı panelde sekme.
 *
 * Yöntemler: Google, Apple, e-posta+parola, telefon+tek kullanımlık kod.
 */
export default function AuthPage() {
  return (
    <div className="relative min-h-svh">
      <AuthAperture />

      {/* Künye — sahnenin üstünde, panellerle birlikte kaymaz */}
      <header className="pointer-events-none fixed inset-x-0 top-0 z-[2] px-[var(--section-gutter)] py-[var(--p-space-4)]">
        <Link
          href="/"
          className="pointer-events-auto inline-flex items-baseline gap-[2px]"
        >
          <span
            className="font-display text-[var(--p-text-md)] leading-none tracking-[-0.05em] text-[var(--ink-title)]"
            style={{ fontWeight: "var(--p-weight-black)" }}
          >
            ARGUS
          </span>
          <span
            className="font-display text-[var(--p-text-md)] leading-none tracking-[-0.03em] text-[var(--ink-mute)]"
            style={{ fontWeight: "var(--p-weight-hair)" }}
          >
            LENS
          </span>
        </Link>

        {/* Dil anahtari — kullanici oturum acmadan once de secebilsin */}
        <div className="pointer-events-auto absolute right-[var(--section-gutter)] top-[var(--p-space-4)]">
          <LocaleSwitch />
        </div>
      </header>

      <main className="auth-scroll">
        <AuthPanels />
      </main>
    </div>
  );
}
