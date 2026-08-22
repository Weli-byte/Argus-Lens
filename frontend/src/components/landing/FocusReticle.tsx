"use client";

import { useEffect, useRef } from "react";

/**
 * Odak nişangâhı — landing'e özel imleç katmanı.
 *
 * Neden: "Optik Enstrüman" yönünde imleç bir ok değil, vizördeki odak
 * noktasıdır. Etkileşimli bir öğenin üzerine gelince halka açılır ve
 * kilitlenir — tıklanabilirliği söyler, süs yapmaz.
 *
 * Kapalı olduğu durumlar: dokunmatik/kaba işaretçi, prefers-reduced-motion.
 * Sistem imleci gizlenmez; nişangâh onun üstüne biner (erişilebilirlik).
 */
export default function FocusReticle() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (!window.matchMedia("(pointer: fine)").matches) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    let x = window.innerWidth / 2;
    let y = window.innerHeight / 2;
    let tx = x;
    let ty = y;
    let raf = 0;
    let shown = false;

    const tick = () => {
      x += (tx - x) * 0.18;
      y += (ty - y) * 0.18;
      el.style.transform = `translate3d(${x}px, ${y}px, 0) translate(-50%, -50%)`;
      raf = requestAnimationFrame(tick);
    };

    const move = (e: PointerEvent) => {
      tx = e.clientX;
      ty = e.clientY;
      if (!shown) {
        shown = true;
        el.dataset.visible = "true";
      }
      const hit = (e.target as HTMLElement | null)?.closest(
        "a, button, [role='button'], input, summary"
      );
      el.dataset.locked = hit ? "true" : "false";
    };

    const leave = () => {
      shown = false;
      el.dataset.visible = "false";
    };

    window.addEventListener("pointermove", move, { passive: true });
    document.addEventListener("pointerleave", leave);
    raf = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", move);
      document.removeEventListener("pointerleave", leave);
    };
  }, []);

  return (
    <div
      ref={ref}
      aria-hidden="true"
      data-visible="false"
      data-locked="false"
      className="reticle"
    >
      <span className="reticle-ring" />
      <span className="reticle-bar reticle-bar-x" />
      <span className="reticle-bar reticle-bar-y" />
    </div>
  );
}
