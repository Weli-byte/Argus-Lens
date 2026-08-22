import Link from "next/link";

const COLUMNS: Array<{ head: string; items: Array<[string, string]> }> = [
  {
    head: "Konsol",
    items: [
      ["Kamera", "/dashboard/vision"],
      ["Tespit", "/dashboard/detection"],
      ["Vital", "/dashboard/vitals"],
      ["Klinik asistan", "/dashboard/chat"],
    ],
  },
  {
    head: "Platform",
    items: [
      ["Teknik künye", "#kunye"],
      ["Sahne 01 — Göz", "#sahne-01"],
      ["Sahne 03 — Tespit", "#sahne-03"],
    ],
  },
];

export default function SiteFooter() {
  return (
    <footer className="section border-t border-[var(--edge-hair)] pb-[var(--p-space-5)]">
      <div
        className="shell grid grid-cols-12 gap-x-[var(--p-space-3)]
                   gap-y-[var(--p-space-5)] lg:gap-x-[var(--p-space-5)]"
      >
        <div className="col-span-12 lg:col-span-5">
          <p className="flex items-baseline gap-[2px]">
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
          </p>
          <p className="t-body mt-[var(--p-space-3)] text-[var(--p-text-sm)]">
            Biyonik lens görü platformu. Klinik karar desteği amaçlıdır;
            tanı yerine geçmez.
          </p>
        </div>

        {COLUMNS.map((col) => (
          <nav
            key={col.head}
            className="col-span-6 lg:col-span-3"
            aria-label={col.head}
          >
            <p className="t-dial mb-[var(--p-space-3)]">{col.head}</p>
            <ul className="space-y-[var(--p-space-2)]">
              {col.items.map(([label, href]) => (
                <li key={href}>
                  <Link
                    href={href}
                    className="t-body text-[var(--p-text-sm)] text-[var(--ink-mute)]
                               transition-colors hover:text-[var(--ink-title)]"
                  >
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        ))}
      </div>

      <div
        className="shell mt-[var(--p-space-6)] flex flex-wrap items-center
                   justify-between gap-[var(--p-space-3)]
                   border-t border-[var(--edge-hair)] pt-[var(--p-space-3)]"
      >
        <p className="t-dial">© 2026 ArgusLens · Tüm hakları saklıdır</p>
        <p className="t-dial">Sanat yönü: Optik Enstrüman · Rev. 4</p>
      </div>
    </footer>
  );
}
