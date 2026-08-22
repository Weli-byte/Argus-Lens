"use client";

import { useEffect, useRef } from "react";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import HudFrame from "./HudFrame";

type Props = {
  /** public/video altındaki dosya kökü, uzantısız. Örn: "01-eye" */
  src: string;
  /** Ekran okuyucu için sahnenin ne gösterdiği. */
  alt: string;
  hudLabel?: string;
  className?: string;
  /** Hero videosu ilk ekranda: poster hemen basılır (LCP adayı). */
  priority?: boolean;
};

/**
 * Sahne videosu.
 *
 * Bant genişliği kuralları:
 *  - preload="none" → viewport'a girene kadar tek bayt video inmez.
 *  - poster da tembel: yalnız hero'da öznitelik olarak basılır, diğerlerinde
 *    ~400px kala JS ile atanır. Aksi hâlde 5 posterin tamamı (~345 KB)
 *    ilk yüklemede iner.
 *  - Görünürken oynar, çıkınca durur → arka planda pil ve GPU yakmaz.
 *  - prefers-reduced-motion / Save-Data → hiç oynamaz, poster kalır.
 *
 * Kaynak 1280x720. .barrel halation + grade yumuşaklığı kasıtlı gösterir.
 * WebM üretilemedi (ffmpeg yok), tek kaynak MP4 — tüm hedef tarayıcılar destekler.
 */
export default function SceneVideo({
  src,
  alt,
  hudLabel,
  className = "",
  priority = false,
}: Props) {
  const ref = useRef<HTMLVideoElement>(null);
  const reduced = useMediaQuery("(prefers-reduced-motion: reduce)");

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const poster = `/poster/${src}.jpg`;
    if (!el.poster) el.poster = poster;

    const conn = (
      navigator as Navigator & { connection?: { saveData?: boolean } }
    ).connection;
    const still = reduced || conn?.saveData === true;

    // Poster: yaklaşırken indir
    const posterIO = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          if (!el.poster) el.poster = poster;
          posterIO.disconnect();
        }
      },
      { rootMargin: "400px" }
    );
    posterIO.observe(el);

    if (still) return () => posterIO.disconnect();

    let playIO: IntersectionObserver | null = null;
    let cancelled = false;

    // Oynatma: sadece gerçekten görünürken
    const armPlayback = () => {
      if (cancelled) return;
      playIO = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) {
            void el.play().catch(() => {
              /* otomatik oynatma engellendi — poster kalır, kırılma yok */
            });
          } else if (!el.paused) {
            el.pause();
          }
        },
        { threshold: 0.25 }
      );
      playIO.observe(el);
    };

    /* Hero videosu ilk ekranda olduğu için gözlemci anında tetikleniyor ve
       ~2.5 MB'lık indirme LCP'nin önüne geçiyordu (ölçüldü: yavaş 4G'de
       FCP 2.4 sn). Poster zaten kadrajı gösterdiğinden oynatmayı `load`
       sonrasına erteliyoruz. Ekran altındaki sahnelerde böyle bir yarış
       yok; onlar hemen kurulur. */
    if (priority && document.readyState !== "complete") {
      window.addEventListener("load", armPlayback, { once: true });
    } else if (priority) {
      window.setTimeout(armPlayback, 200);
    } else {
      armPlayback();
    }

    return () => {
      cancelled = true;
      posterIO.disconnect();
      playIO?.disconnect();
      window.removeEventListener("load", armPlayback);
    };
  }, [src, priority, reduced]);

  return (
    <div className={`barrel ${className}`}>
      <video
        ref={ref}
        className="block h-full w-full object-cover"
        muted
        loop
        playsInline
        preload="none"
        poster={priority ? `/poster/${src}.jpg` : undefined}
        aria-label={alt}
        tabIndex={-1}
        controls={false}
        {...(priority ? { "data-priority": "true" } : {})}
      >
        <source src={`/video/${src}.mp4`} type="video/mp4" />
      </video>
      <HudFrame label={hudLabel} />
      {reduced ? (
        <span className="visually-hidden">
          {alt} — hareket azaltma tercihiniz nedeniyle sabit kare gösteriliyor.
        </span>
      ) : (
        <span className="visually-hidden">{alt}</span>
      )}
    </div>
  );
}
