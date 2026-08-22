"use client";

import { useEffect, useRef } from "react";
import { Camera } from "lucide-react";
import SceneVideo from "@/components/landing/SceneVideo";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { useT } from "@/lib/i18n";

/* ────────────────────────────────────────────────────────────────────────────
   KAMERA — BEKLEME SAHNESİ

   Kamera kapalıyken burası boş bir siyah kutu değil, kapalı bir vizör.
   Zemin: `gözü_gösterdikten_sonra_hemen.mp4` (repoda 05-act.mp4 — istenen
   dosyayla byte-byte aynı, MD5 doğrulandı).

   Hareket dili landing ile aynı: ODAK KAYDIRMA. Hiçbir şey aşağıdan yukarı
   kaymaz.
     - Fare: görüntü, HUD ve metin farklı katsayılarla kayar → derinlik
     - Açılış: diyafram açılır gibi bulanıktan nete gelir
     - Tekerlek: sahne ekseninde çok az iter (kaydırma hissi, sayfa kaymaz)

   prefers-reduced-motion: tüm hareket kapanır, video oynamaz, poster kalır,
   başlat düğmesi tam çalışır.
   ────────────────────────────────────────────────────────────────────────── */

export default function CameraIdleStage({ onStart }: { onStart: () => void }) {
  const rootRef = useRef<HTMLDivElement>(null);
  const t = useT();
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
    let wheelTarget = 0;
    let wheel = 0;
    let raf = 0;
    const started = performance.now();

    const onPointer = (e: PointerEvent) => {
      const r = root.getBoundingClientRect();
      tx = ((e.clientX - r.left) / r.width) * 2 - 1;
      ty = ((e.clientY - r.top) / r.height) * 2 - 1;
    };

    /* Tekerlek sahneyi ekseninde iter. Sayfa kaydırmasını ÇALMAZ —
       preventDefault yok; yalnız görsel derinlik ekler. */
    const onWheel = (e: WheelEvent) => {
      wheelTarget = Math.max(-1, Math.min(1, wheelTarget + e.deltaY * 0.0016));
    };

    const tick = (now: number) => {
      const t = Math.min(1, (now - started) / 1100);
      root.style.setProperty("--op", (1 - Math.pow(1 - t, 3)).toFixed(4));
      x += (tx - x) * 0.07;
      y += (ty - y) * 0.07;
      wheelTarget *= 0.94; // yay gibi merkeze döner
      wheel += (wheelTarget - wheel) * 0.09;
      root.style.setProperty("--px", x.toFixed(4));
      root.style.setProperty("--py", y.toFixed(4));
      root.style.setProperty("--wz", wheel.toFixed(4));
      raf = requestAnimationFrame(tick);
    };

    if (!coarse) root.addEventListener("pointermove", onPointer, { passive: true });
    root.addEventListener("wheel", onWheel, { passive: true });
    raf = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(raf);
      root.removeEventListener("pointermove", onPointer);
      root.removeEventListener("wheel", onWheel);
    };
  }, [reduced, coarse]);

  return (
    <div ref={rootRef} className="vis-idle">
      <div className="vis-idle-video" aria-hidden="true">
        <SceneVideo
          src="05-act"
          alt=""
          className="barrel-bleed h-full w-full"
          hudLabel="KAM 00 · BEKLEME"
          priority
        />
      </div>

      <div className="vis-idle-wash" aria-hidden="true" />

      <div className="vis-idle-body">
        <p className="t-dial vis-idle-kicker">
          <span className="vis-dot" aria-hidden="true" />
          {t("Sensör hazır · Yayın kapalı")}
        </p>

        <h2 className="vis-idle-title">
          {t("KAREYİ")} <span className="t-counter">{t("aç")}</span>
        </h2>

        <p className="vis-idle-copy">
          {t(
            "Kamera açıldığında görüntü tespit ve vital katmanlarıyla birlikte işlenir. Hiçbir kare cihazdan çıkmadan önce filtreden geçer."
          )}
        </p>

        <button onClick={onStart} className="btn btn-primary vis-start">
          <Camera className="size-4" />
          {t("Kamerayı başlat")}
        </button>
      </div>
    </div>
  );
}
