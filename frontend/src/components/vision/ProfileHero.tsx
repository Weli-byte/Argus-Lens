"use client";

import { useEffect, useRef } from "react";
import SceneVideo from "@/components/landing/SceneVideo";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { useT } from "@/lib/i18n";

/* ────────────────────────────────────────────────────────────────────────────
   SAĞLIK PROFİLİ — BAŞLIK SAHNESİ

   Zemin: `gözü_gösterdikten_sonra_hemen.mp4` (repoda 05-act.mp4).
   İki dosya olarak verilen klip byte-byte aynıydı (MD5 doğrulandı), tek video.

   Hareket dili konsolun geri kalanıyla aynı: fare paralaksı + odak kaydırma.
   Sayfa kaydırıldıkça başlık geride kalır (parallaks derinlik).
   ────────────────────────────────────────────────────────────────────────── */

type Props = {
  /** Künyede gösterilecek kısa ölçümler — cyan yalnız burada. */
  cells?: string[];
  kicker: string;
  title: React.ReactNode;
  copy: string;
};

export default function ProfileHero({ cells, kicker, title, copy }: Props) {
  const t = useT();
  const rootRef = useRef<HTMLDivElement>(null);
  const reduced = useMediaQuery("(prefers-reduced-motion: reduce)");
  const coarse = useMediaQuery("(pointer: coarse)");

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;

    if (reduced) {
      root.style.setProperty("--op", "1");
      return;
    }

    let tx = 0;
    let ty = 0;
    let x = 0;
    let y = 0;
    let sTarget = 0;
    let sNow = 0;
    let raf = 0;
    const started = performance.now();

    const onPointer = (e: PointerEvent) => {
      const r = root.getBoundingClientRect();
      tx = ((e.clientX - r.left) / r.width) * 2 - 1;
      ty = ((e.clientY - r.top) / r.height) * 2 - 1;
    };

    /* Sayfa kaydıkça başlık geride kalır.
       Gerçek scroller sabit değil: konsol düzeninde `main`, başka yerde
       sayfanın kendisi olabiliyor. En yakın GERÇEKTEN kaydırılabilir atayı
       arıyoruz; sabit bir seçici kullanmak sessizce çalışmamasına yol açtı. */
    const findScroller = (el: HTMLElement | null): HTMLElement | null => {
      let n = el?.parentElement ?? null;
      while (n) {
        const oy = getComputedStyle(n).overflowY;
        if ((oy === "auto" || oy === "scroll") && n.scrollHeight > n.clientHeight + 4) {
          return n;
        }
        n = n.parentElement;
      }
      return null;
    };
    const scroller = findScroller(root);
    const onScroll = () => {
      const top = scroller ? scroller.scrollTop : window.scrollY;
      sTarget = Math.min(1, top / 420);
    };

    const tick = (now: number) => {
      const t = Math.min(1, (now - started) / 1100);
      root.style.setProperty("--op", (1 - Math.pow(1 - t, 3)).toFixed(4));
      x += (tx - x) * 0.07;
      y += (ty - y) * 0.07;
      sNow += (sTarget - sNow) * 0.1;
      root.style.setProperty("--px", x.toFixed(4));
      root.style.setProperty("--py", y.toFixed(4));
      root.style.setProperty("--sp", sNow.toFixed(4));
      raf = requestAnimationFrame(tick);
    };

    if (!coarse) root.addEventListener("pointermove", onPointer, { passive: true });
    (scroller ?? window).addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    raf = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(raf);
      root.removeEventListener("pointermove", onPointer);
      (scroller ?? window).removeEventListener("scroll", onScroll);
    };
  }, [reduced, coarse]);

  return (
    <header ref={rootRef} className="vis-idle prof-hero">
      <div className="vis-idle-video" aria-hidden="true">
        <SceneVideo
          src="05-act"
          alt=""
          className="barrel-bleed h-full w-full"
          hudLabel={t("KAYIT · SAĞLIK PROFİLİ")}
          priority
        />
      </div>

      <div className="vis-idle-wash" aria-hidden="true" />

      <div className="vis-idle-body prof-hero-body">
        <p className="t-dial vis-idle-kicker">
          <span className="vis-dot" aria-hidden="true" />
          {kicker}
        </p>

        <h1 className="vis-idle-title">{title}</h1>

        <p className="vis-idle-copy">{copy}</p>

        {cells && cells.length > 0 && (
          <p className="mt-[var(--p-space-2)] flex flex-wrap gap-[var(--p-space-2)]">
            {cells.map((c) => (
              <span key={c} className="cell">
                {c}
              </span>
            ))}
          </p>
        )}
      </div>
    </header>
  );
}
