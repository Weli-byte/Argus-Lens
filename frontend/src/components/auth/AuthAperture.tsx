"use client";

import { useEffect, useRef } from "react";
import SceneVideo from "@/components/landing/SceneVideo";
import { useMediaQuery } from "@/hooks/useMediaQuery";

/* ────────────────────────────────────────────────────────────────────────────
   KİMLİK SAHNESİ

   Video ekranın SOL yarısında ve kadrajın TAMAMI görünür (`object-fit:
   contain`). Daha önce `cover` kullanılıyordu ve kenarlar kırpılıyordu.

   Fare hareketi göze bağlanır: kutu 3B eğilir (rotateX/rotateY) ve görüntü
   imlecin ters yönünde çok az kayar. İkisi birleşince göz imleci takip
   ediyormuş gibi görünür — kadrajın hiçbir kenarı açığa çıkmaz çünkü eğim
   perspektiften geliyor, kırpmadan değil.

   Kalibrasyon halkası / f-durakları / nişangâh KALDIRILDI: görüntünün önünü
   kapatıyordu.

   --px/--py : imleç (-1 … 1)
   --op      : açılış (0 → 1)
   ────────────────────────────────────────────────────────────────────────── */

export default function AuthAperture() {
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
    let raf = 0;
    const started = performance.now();

    const onPointer = (e: PointerEvent) => {
      tx = (e.clientX / window.innerWidth) * 2 - 1;
      ty = (e.clientY / window.innerHeight) * 2 - 1;
    };

    const tick = (now: number) => {
      const t = Math.min(1, (now - started) / 1100);
      root.style.setProperty("--op", (1 - Math.pow(1 - t, 3)).toFixed(4));
      // Yumuşatma: imleç sıçraması göze birebir yansımasın
      x += (tx - x) * 0.075;
      y += (ty - y) * 0.075;
      root.style.setProperty("--px", x.toFixed(4));
      root.style.setProperty("--py", y.toFixed(4));
      raf = requestAnimationFrame(tick);
    };

    if (!coarse) {
      window.addEventListener("pointermove", onPointer, { passive: true });
    }
    raf = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", onPointer);
    };
  }, [reduced, coarse]);

  return (
    <div ref={rootRef} className="ap-stage" aria-hidden="true">
      <div className="ap-ground" />
      <div className="ap-flare" />

      {/* Sol yarı: kadrajın tamamı görünen göz */}
      <div className="ap-eye-slot">
        <div className="ap-eye">
          <SceneVideo
            src="01-eye"
            alt=""
            className="barrel-bleed h-full w-full"
            priority
          />
        </div>
      </div>

      <div className="ap-wash" />
      <div className="ap-vignette" />
      <div className="optic-grain" />
    </div>
  );
}
