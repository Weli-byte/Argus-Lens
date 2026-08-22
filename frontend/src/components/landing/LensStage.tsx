"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import { useMediaQuery, useWebGLSupport } from "@/hooks/useMediaQuery";

/* three + @react-three/fiber ilk pakete GİRMEZ. Yalnızca sahne gerçekten
   çalışacaksa indirilir. */
const LensScene = dynamic(() => import("./LensScene"), { ssr: false });

/**
 * 3D katmanının kapısı.
 *
 * Sahne SADECE şu koşullar sağlanınca yüklenir:
 *   - viewport'a girmişse (IntersectionObserver)
 *   - prefers-reduced-motion: reduce DEĞİLSE
 *   - ekran 860px'ten genişse (mobilde pil ve bant genişliği)
 *   - WebGL varsa
 *
 * Aksi hâlde statik optik diyagram gösterilir — sayfa boş kalmaz,
 * anlatı 3D olmadan da tamamdır.
 */
export default function LensStage() {
  const hostRef = useRef<HTMLDivElement>(null);
  const [mount, setMount] = useState(false);

  const reduced = useMediaQuery("(prefers-reduced-motion: reduce)");
  const narrow = useMediaQuery("(max-width: 860px)");
  const webgl = useWebGLSupport();
  const eligible = !reduced && !narrow && webgl;

  useEffect(() => {
    if (!eligible) return;
    const host = hostRef.current;
    if (!host) return;

    let io: IntersectionObserver | null = null;
    let cancelled = false;

    /* three.js parçası ~227 KB gzip. Hero zaten viewport'ta olduğu için
       gözlemci hemen tetiklenir ve indirme LCP boyamasının önüne geçer
       (ölçüldü: render gecikmesi +1.1 sn). Bu yüzden kurulum `load`
       sonrasına, oradan da boşta zamana ertelenir. 3D dekoratiftir;
       ilk boyamanın önünde durmamalı. */
    const arm = () => {
      if (cancelled || !hostRef.current) return;
      io = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) {
            setMount(true);
            io?.disconnect();
          }
        },
        { rootMargin: "120px" }
      );
      io.observe(hostRef.current);
    };

    const idle = (cb: () => void) => {
      const ric = (
        window as Window & {
          requestIdleCallback?: (cb: () => void, o?: { timeout: number }) => number;
        }
      ).requestIdleCallback;
      if (ric) ric(cb, { timeout: 2500 });
      else window.setTimeout(cb, 600);
    };

    if (document.readyState === "complete") {
      idle(arm);
    } else {
      window.addEventListener("load", () => idle(arm), { once: true });
    }

    return () => {
      cancelled = true;
      io?.disconnect();
    };
  }, [eligible]);

  return (
    <div
      ref={hostRef}
      className="pointer-events-none absolute inset-0 z-0"
      aria-hidden="true"
    >
      {mount ? <LensScene /> : <StaticOptic />}
    </div>
  );
}

/** 3D yokken gösterilen statik optik diyagram — patlatılmış eleman şeması. */
function StaticOptic() {
  return (
    <div className="absolute inset-0 grid place-items-center">
      <div className="relative aspect-square w-[min(52vh,42vw)] max-w-full opacity-45">
        <span className="aperture absolute inset-0" />
        <span className="aperture absolute inset-[14%] opacity-70" />
        <span className="aperture absolute inset-[30%] opacity-45" />
        <span className="aperture absolute inset-[46%] opacity-25" />
      </div>
    </div>
  );
}
