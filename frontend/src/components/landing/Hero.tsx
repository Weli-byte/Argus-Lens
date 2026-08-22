import Link from "next/link";
import { preload } from "react-dom";
import SceneVideo from "./SceneVideo";
import LensStage from "./LensStage";

/**
 * Sahne 01 — GÖZ.
 * Kompozisyon: ortalanmış tek sütun DEĞİL. 12 kolonluk ızgarada metin
 * 2-8 arası, ölçüm bloğu sağ altta, kadran etiketi sol altta.
 * Katman sırası: video (zemin) → 3D mercek yığını → HUD → metin.
 */
export default function Hero() {
  /* LCP adayı hero posteridir. <video poster> layout'a kadar keşfedilmez;
     JSX içindeki <link> ise yalnız istemcide hoist ediliyor. ReactDOM.preload
     sunucu HTML'ine gerçek preload satırını yazar. */
  preload("/poster/01-eye.jpg", { as: "image", fetchPriority: "high" });

  return (
    <section
      id="sahne-01"
      data-scene="01"
      className="relative flex min-h-[100svh] items-end overflow-hidden
                 px-[var(--section-gutter)] pb-[var(--p-space-7)]
                 pt-[var(--p-space-8)]"
    >
      {/* Zemin: göz videosu, tam kaplama */}
      <div className="absolute inset-0 -z-10">
        <SceneVideo
          src="01-eye"
          alt="İnsan gözünün tam karşıdan makro çekimi; iris üzerinde ölçüm katmanı beliriyor"
          className="grade-optic barrel-bleed h-full w-full"
          priority
        />
      </div>

      {/* 3D mercek yığını — viewport'a girmeden init olmaz */}
      <LensStage />

      <div className="shell relative z-10 grid grid-cols-12 items-end gap-y-[var(--p-space-5)]">
        <div className="col-span-12 md:col-span-8 lg:col-span-7">
          <p
            className="t-dial mb-[var(--p-space-4)] flex flex-wrap items-center
                       gap-x-[var(--p-space-3)] gap-y-[var(--p-space-1)]"
            data-reveal="boot"
          >
            <span className="text-[var(--measure)]">KAM 01 · İRİS</span>
            <span aria-hidden="true">/</span>
            <span>ArgusLens · Biyonik lens görü platformu · Sürüm 4</span>
          </p>

          <h1 className="t-display" data-reveal="boot" style={{ "--reveal-delay": "90ms" } as React.CSSProperties}>
            GÖZ <span className="t-counter">artık</span>
            <br />
            BİR ARAYÜZ
          </h1>

          <p
            className="t-body mt-[var(--p-space-4)]"
            data-reveal="boot"
            style={{ "--reveal-delay": "180ms" } as React.CSSProperties}
          >
            Retinaya oturan lens gördüğünü kaydetmez — okur. Nesne tespiti,
            vital telemetri ve klinik yorumlama tek optik hat üzerinde,
            kareyi bırakmadan.
          </p>

          <div
            className="mt-[var(--p-space-5)] flex flex-wrap gap-[var(--p-space-3)]"
            data-reveal="boot"
            style={{ "--reveal-delay": "270ms" } as React.CSSProperties}
          >
            <Link href="/login" className="btn btn-primary">
              Konsola gir
            </Link>
            <a href="#sahne-02" className="btn btn-ghost">
              Hattı izle
            </a>
          </div>
        </div>

        {/* Ölçüm bloğu — sağ altta, cyan yalnız burada */}
        <div
          className="col-span-12 flex flex-wrap items-end gap-[var(--p-space-2)]
                     md:col-span-4 md:justify-end lg:col-span-5"
          data-reveal="boot"
          style={{ "--reveal-delay": "360ms" } as React.CSSProperties}
        >
          <span className="cell">60 FPS</span>
          <span className="cell">INFERENCE 24 MS</span>
          <span className="cell">RTT 8 MS</span>
        </div>
      </div>

      {/* Kadran: kaydırma göstergesi — sağ altta, buton sırasıyla çakışmaz */}
      <p
        className="t-dial absolute bottom-[var(--p-space-4)]
                   right-[var(--section-gutter)] flex items-center
                   gap-[var(--p-space-2)]"
      >
        <span aria-hidden="true">↓</span>
        Aşağı kaydır · Odak 01 / 05
      </p>
    </section>
  );
}
