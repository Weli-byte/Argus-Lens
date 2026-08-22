"use client";

import { useEffect, useRef } from "react";
import { Upload } from "lucide-react";
import SceneVideo from "@/components/landing/SceneVideo";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { useT } from "@/lib/i18n";

/* ────────────────────────────────────────────────────────────────────────────
   NESNE TESPİTİ — BIRAKMA SAHNESİ

   Boş bırakma alanı yerine işin kendisini gösteren zemin:
   `nesnelerin_üzerinde_oranlarda.mp4` (repoda 03-detect.mp4 — istenen
   dosyayla byte-byte aynı, MD5 doğrulandı). Klipte nesnelerin üstünde
   güven oranlarıyla tespit kutuları var; kullanıcı daha yüklemeden
   çıktının neye benzeyeceğini görüyor.

   Hareket dili kamera sayfasıyla aynı: odak kaydırma + fare paralaksı.
   Sürükleme sırasında diyafram açılır gibi zemin netleşir.
   ────────────────────────────────────────────────────────────────────────── */

type Props = {
  dragOver: boolean;
  onPick: () => void;
};

export default function DetectDropStage({ dragOver, onPick }: Props) {
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
    let raf = 0;
    const started = performance.now();

    const onPointer = (e: PointerEvent) => {
      const r = root.getBoundingClientRect();
      tx = ((e.clientX - r.left) / r.width) * 2 - 1;
      ty = ((e.clientY - r.top) / r.height) * 2 - 1;
    };

    const tick = (now: number) => {
      const t = Math.min(1, (now - started) / 1100);
      root.style.setProperty("--op", (1 - Math.pow(1 - t, 3)).toFixed(4));
      x += (tx - x) * 0.07;
      y += (ty - y) * 0.07;
      root.style.setProperty("--px", x.toFixed(4));
      root.style.setProperty("--py", y.toFixed(4));
      raf = requestAnimationFrame(tick);
    };

    if (!coarse) root.addEventListener("pointermove", onPointer, { passive: true });
    raf = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(raf);
      root.removeEventListener("pointermove", onPointer);
    };
  }, [reduced, coarse]);

  return (
    <div
      ref={rootRef}
      className="vis-idle vis-drop"
      data-drag={dragOver ? "true" : undefined}
      onClick={onPick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onPick();
        }
      }}
      aria-label={t("Görsel yükle veya sürükleyip bırak")}
    >
      <div className="vis-idle-video" aria-hidden="true">
        <SceneVideo
          src="03-detect"
          alt=""
          className="barrel-bleed h-full w-full"
          hudLabel={t("KAM 03 · TESPİT")}
          priority
        />
      </div>

      <div className="vis-idle-wash" aria-hidden="true" />

      <div className="vis-idle-body vis-drop-body">
        <span className="vis-drop-mark" aria-hidden="true">
          <Upload className="size-8" strokeWidth={1.5} />
        </span>

        <p className="t-dial vis-idle-kicker">
          <span className="vis-dot" aria-hidden="true" />
          {t("Kaynak bekleniyor")}
        </p>

        <h2 className="vis-idle-title">
          {t("GÖRSEL")} <span className="t-counter">{t("bırak")}</span>
        </h2>

        <p className="vis-idle-copy">
          {t(
            "Sürükleyip bırakın veya tıklayıp seçin. JPG, PNG, WebP — en fazla 10 MB. Görsel cihazdan çıkmadan önce tespit hattına girer."
          )}
        </p>
      </div>
    </div>
  );
}
