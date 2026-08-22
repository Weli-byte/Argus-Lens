"use client";

import { useLocale, type Locale } from "@/lib/i18n";

/* ────────────────────────────────────────────────────────────────────────────
   DİL ANAHTARI — TR / EN

   Enstrüman dili: iki hücreli plaka, altında kayan bir işaretçi. Sidebar'daki
   aktif göstergeyle aynı mantık — seçim amber, çünkü palet kuralında amber
   "durum + aktif seçim", cyan yalnız ÖLÇÜLMÜŞ değer.

   İşaretçi React state ile değil CSS değişkeniyle konumlanıyor; iki hücre
   olduğu için `--i` 0 veya 1.
   ────────────────────────────────────────────────────────────────────────── */

const OPTIONS: { code: Locale; label: string; full: string }[] = [
  { code: "tr", label: "TR", full: "Türkçe" },
  { code: "en", label: "EN", full: "English" },
];

export default function LocaleSwitch() {
  const { locale, setLocale } = useLocale();
  const index = locale === "en" ? 1 : 0;

  return (
    <div
      className="lang-switch"
      role="group"
      aria-label={locale === "en" ? "Language" : "Dil"}
      style={{ ["--i" as string]: index }}
    >
      <span className="lang-switch-marker" aria-hidden="true" />
      {OPTIONS.map((o) => (
        <button
          key={o.code}
          type="button"
          lang={o.code}
          onClick={() => setLocale(o.code)}
          aria-pressed={locale === o.code}
          title={o.full}
          className="lang-switch-cell"
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
