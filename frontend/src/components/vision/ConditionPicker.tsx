"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { Search } from "lucide-react";
import { useT } from "@/lib/i18n";

/* ────────────────────────────────────────────────────────────────────────────
   HASTALIK SEÇİCİ — arama + klavye

   22 durum uzun bir liste; fareyle kaydırmadan bulmak mümkün değildi.
     - yazdıkça filtreler (ad + etiket üzerinde)
     - ↑ ↓ gezinir, Enter seçer, Esc aramayı temizler
     - `/` sayfanın herhangi bir yerinden arama alanına odaklanır

   Klavyeyle kullanılabilirlik premium arayüzlerin ayırt edici özelliği;
   burada aynı zamanda erişilebilirlik kazancı (listbox semantiği).
   ────────────────────────────────────────────────────────────────────────── */

export type PickerItem = {
  id: string;
  name: string;
  label: string;
  group: string;
};

type Props = {
  items: PickerItem[];
  activeId: string;
  onSelect: (id: string) => void;
};

/** Türkçe arama: İ/ı/ş/ğ farkını yok sayar. */
function fold(v: string): string {
  return v
    .toLocaleLowerCase("tr")
    .replace(/ı/g, "i")
    .replace(/ş/g, "s")
    .replace(/ğ/g, "g")
    .replace(/ü/g, "u")
    .replace(/ö/g, "o")
    .replace(/ç/g, "c");
}

export default function ConditionPicker({ items, activeId, onSelect }: Props) {
  const t = useT();
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const filtered = useMemo(() => {
    const q = fold(query.trim());
    if (!q) return items;
    return items.filter(
      (i) => fold(i.name).includes(q) || fold(i.label).includes(q)
    );
  }, [items, query]);

  // `/` ile aramaya odaklan
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "/") return;
      const t = e.target as HTMLElement | null;
      if (t && /^(INPUT|TEXTAREA)$/.test(t.tagName)) return;
      e.preventDefault();
      inputRef.current?.focus();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  /* İmleç listeden taşmasın. Efektle setState yerine render sırasında
     türetiliyor — efekt gövdesinde senkron setState zincirleme render
     uyarısı veriyor ve bir kare geç düzeltiyordu. */
  const safe = Math.min(cursor, Math.max(0, filtered.length - 1));

  const move = (delta: number) => {
    if (filtered.length === 0) return;
    const next = (safe + delta + filtered.length) % filtered.length;
    setCursor(next);
    const el = listRef.current?.querySelectorAll("[data-cond]")[next];
    el?.scrollIntoView({ block: "nearest" });
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      move(1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      move(-1);
    } else if (e.key === "Enter") {
      e.preventDefault();
      const item = filtered[safe];
      if (item) onSelect(item.id);
    } else if (e.key === "Escape") {
      setQuery("");
    }
  };

  // Gruplara böl (arama yokken); aramada düz liste
  const grouped = useMemo(() => {
    if (query.trim()) return [{ group: "", items: filtered }];
    const out: { group: string; items: PickerItem[] }[] = [];
    filtered.forEach((i) => {
      const last = out[out.length - 1];
      if (last && last.group === i.group) last.items.push(i);
      else out.push({ group: i.group, items: [i] });
    });
    return out;
  }, [filtered, query]);

  let flat = -1;

  return (
    <>
      <div className="vis-search">
        <Search className="size-3.5 shrink-0 text-[var(--ink-faint)]" />
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={t("Ara — miyop, katarakt…")}
          aria-label={t("Göz durumu ara")}
          className="vis-search-input"
        />
        <kbd className="vis-kbd">/</kbd>
      </div>

      <div
        ref={listRef}
        className="vis-scroll mt-[var(--p-space-3)] space-y-[var(--p-space-4)] max-h-[46vh]"
        role="listbox"
        aria-label={t("Göz durumları")}
      >
        {filtered.length === 0 && (
          <p className="t-dial px-[var(--p-space-2)] py-[var(--p-space-4)]">
            {t("Eşleşme yok")}
          </p>
        )}

        {grouped.map((g) => (
          <div key={g.group || "sonuc"}>
            {g.group && <p className="vis-group-label">{g.group}</p>}
            <div className="space-y-[var(--p-space-1)]">
              {g.items.map((item) => {
                flat += 1;
                const idx = flat;
                const selected = activeId === item.id;
                return (
                  <button
                    key={item.id}
                    role="option"
                    aria-selected={selected}
                    data-cond
                    data-cursor={idx === safe ? "true" : undefined}
                    onClick={() => onSelect(item.id)}
                    onMouseEnter={() => setCursor(idx)}
                    className="vis-cond"
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="vis-cond-name">{item.name}</span>
                      {selected && (
                        <span className="size-1.5 shrink-0 rounded-full bg-[var(--accent-status)]" />
                      )}
                    </span>
                    <span className="vis-cond-label">{item.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
