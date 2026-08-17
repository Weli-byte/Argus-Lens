"use client";

import React, { useEffect, useRef } from "react";

/**
 * Cyan glow ring that trails the cursor and grows over interactive elements,
 * plus an expanding ripple on every click. Decorative only — the native
 * cursor stays visible. Disabled on touch devices.
 */
export default function CustomCursor() {
  const ringRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (window.matchMedia("(pointer: coarse)").matches) return;

    const ring = ringRef.current;
    if (!ring) return;

    let x = -100;
    let y = -100;
    let rx = -100;
    let ry = -100;
    let raf = 0;
    let hovering = false;

    const onMove = (e: MouseEvent) => {
      x = e.clientX;
      y = e.clientY;
      const target = e.target as HTMLElement;
      hovering = !!target.closest(
        "a, button, [role='button'], input, select, textarea, label, [onclick]"
      );
    };

    const tick = () => {
      rx += (x - rx) * 0.18;
      ry += (y - ry) * 0.18;
      const scale = hovering ? 1.8 : 1;
      ring.style.transform = `translate(${rx - 16}px, ${ry - 16}px) scale(${scale})`;
      ring.style.borderColor = hovering
        ? "rgba(0,212,255,0.7)"
        : "rgba(0,212,255,0.35)";
      raf = requestAnimationFrame(tick);
    };

    const onClick = (e: MouseEvent) => {
      const ripple = document.createElement("div");
      ripple.style.cssText = `
        position: fixed; left: ${e.clientX}px; top: ${e.clientY}px;
        width: 8px; height: 8px; margin: -4px 0 0 -4px;
        border: 2px solid rgba(0,212,255,0.6); border-radius: 50%;
        pointer-events: none; z-index: 9999;
        animation: cursorRipple 0.6s ease-out forwards;
      `;
      document.body.appendChild(ripple);
      setTimeout(() => ripple.remove(), 650);
    };

    window.addEventListener("mousemove", onMove, { passive: true });
    window.addEventListener("click", onClick, { passive: true });
    raf = requestAnimationFrame(tick);

    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("click", onClick);
      cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <div
      ref={ringRef}
      aria-hidden
      className="fixed left-0 top-0 z-[9998] pointer-events-none hidden md:block"
      style={{
        width: 32,
        height: 32,
        borderRadius: "50%",
        border: "1.5px solid rgba(0,212,255,0.35)",
        boxShadow: "0 0 12px rgba(0,212,255,0.25)",
        transition: "border-color 0.2s ease",
        willChange: "transform",
      }}
    />
  );
}
