import Link from "next/link";

/**
 * Kapanış. Diyafram halkası ortada değil — tipografi sola dayalı,
 * halka sağ üstte kadraj işareti gibi durur.
 */
export default function ClosingCTA() {
  return (
    <section id="giris" className="section relative overflow-hidden">
      <div
        className="shell relative grid grid-cols-12 items-center
                   gap-x-0 gap-y-[var(--p-space-5)]
                   lg:gap-x-[var(--p-space-5)]"
      >
        <div className="col-span-12 lg:col-span-8">
          <p className="t-dial mb-[var(--p-space-4)]">Odak 05 / 05 · Devir</p>
          <h2 className="t-display" data-reveal>
            HATTI <span className="t-counter">devral</span>
          </h2>
          <p
            className="t-body mt-[var(--p-space-4)]"
            data-reveal
            style={{ "--reveal-delay": "120ms" } as React.CSSProperties}
          >
            Operatör konsolu canlı kareyi, tespit katmanını ve vital akışını
            tek ekranda birleştirir. Backend kapalıyken de arayüz açılır;
            veri alanları boş kalır.
          </p>
          <div
            className="mt-[var(--p-space-5)] flex flex-wrap gap-[var(--p-space-3)]"
            data-reveal
            style={{ "--reveal-delay": "220ms" } as React.CSSProperties}
          >
            <Link href="/login" className="btn btn-primary">
              Konsola gir
            </Link>
            <a href="#kunye" className="btn btn-ghost">
              Teknik künye
            </a>
          </div>
        </div>

        {/* Diyafram halkası — dekor değil, kadraj işareti */}
        <div
          className="col-span-12 flex justify-start lg:col-span-4 lg:justify-end"
          aria-hidden="true"
        >
          <div className="aperture relative aspect-square w-[var(--p-space-9)] max-w-full">
            <div className="aperture absolute inset-[12%] opacity-60" />
            <div className="aperture absolute inset-[26%] opacity-35" />
            <span className="t-measure absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
              f/1.4
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}
