"use client";

import { useSyncExternalStore } from "react";

const EMPTY = () => () => {};

/**
 * Medya sorgusunu efekt içinde setState çağırmadan okur.
 *
 * Neden useEffect + useState değil: efekt gövdesinde setState zincirleme
 * render tetikler (react-hooks/set-state-in-effect). useSyncExternalStore
 * hem bunu önler hem de sorgu sonradan değişirse (kullanıcı sistem
 * ayarından hareket azaltmayı açarsa) bileşeni günceller.
 *
 * Sunucu anlık görüntüsü daima false: hydration uyuşmazlığı olmaz,
 * hareket/3D yalnızca istemcide açılır.
 */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      if (typeof window === "undefined") return EMPTY();
      const mql = window.matchMedia(query);
      mql.addEventListener("change", onChange);
      return () => mql.removeEventListener("change", onChange);
    },
    () => window.matchMedia(query).matches,
    () => false
  );
}

let webglSupport: boolean | null = null;

function detectWebGL(): boolean {
  if (webglSupport !== null) return webglSupport;
  try {
    const c = document.createElement("canvas");
    webglSupport = !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    webglSupport = false;
  }
  return webglSupport;
}

/** WebGL desteği — sonuç modül düzeyinde önbelleklenir, tek kez ölçülür. */
export function useWebGLSupport(): boolean {
  return useSyncExternalStore(EMPTY, detectWebGL, () => false);
}
