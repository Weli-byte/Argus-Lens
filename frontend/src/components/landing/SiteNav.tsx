import Link from "next/link";

/**
 * Alet üstü künye şeridi. Ortalanmış menü değil — solda marka, sağda durum
 * ve giriş. Altında tek gravür çizgisi.
 * Marka kilidinde ağırlık kontrastı: ARGUS 800 / LENS 200.
 */
export default function SiteNav() {
  return (
    // Cam kart bulanıklığı yok: künye şeridi altındaki görüntüyü bulandırmaz,
    // sadece kendi zeminiyle örter.
    <header
      className="fixed inset-x-0 top-0 z-50 border-b border-[var(--edge-hair)]
                 bg-[color-mix(in_oklch,var(--surface-ground)_92%,transparent)]"
    >
      <nav
        className="mx-auto flex max-w-[var(--content-max)] items-center justify-between
                   gap-[var(--p-space-4)] px-[var(--section-gutter)]
                   py-[var(--p-space-3)]"
        aria-label="Ana gezinme"
      >
        <Link href="/" className="flex items-baseline gap-[2px]">
          <span
            className="font-display text-[var(--p-text-md)] leading-none
                       tracking-[-0.05em] text-[var(--ink-title)]"
            style={{ fontWeight: "var(--p-weight-black)" }}
          >
            ARGUS
          </span>
          <span
            className="font-display text-[var(--p-text-md)] leading-none
                       tracking-[-0.03em] text-[var(--ink-mute)]"
            style={{ fontWeight: "var(--p-weight-hair)" }}
          >
            LENS
          </span>
        </Link>

        <div className="flex items-center gap-[var(--p-space-4)]">
          <span className="hidden sm:block">
            <span className="cell" data-measure>
              <span
                className="aperture inline-block h-[6px] w-[6px]
                           bg-[var(--measure)] p-0"
                aria-hidden="true"
              />
              HAT AKTİF
            </span>
          </span>
          <Link href="/login" className="btn btn-ghost">
            Konsola gir
          </Link>
        </div>
      </nav>
    </header>
  );
}
