"use client";

import { useEffect } from "react";

/**
 * `[data-reveal-block]` bölümleri kaydırdıkça odağa getirir.
 *
 * Gözlemcinin kökü sayfa değil, profilin KENDİ kaydırma kabı
 * (`[data-profile-scroll]`) — konsol düzeninde sayfa değil `main` kayıyor,
 * varsayılan kök kullanılsaydı hiç tetiklenmezdi.
 *
 * prefers-reduced-motion: hepsi anında görünür, gözlemci kurulmaz.
 */
export default function RevealBlocks() {
  useEffect(() => {
    const items = Array.from(
      document.querySelectorAll<HTMLElement>("[data-reveal-block]")
    );
    if (items.length === 0) return;

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      items.forEach((el) => el.classList.add("in-focus"));
      return;
    }

    /* Kök = viewport. Bloklar kendi kaplarinin ICINDE degil, sayfayla
       BIRLIKTE kayiyor; sabit bir kap secmek gozlemciyi sessizce
       calismaz hale getiriyordu. */
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("in-focus");
            io.unobserve(e.target);
          }
        });
      },
      { threshold: 0.08, rootMargin: "0px 0px -6% 0px" }
    );
    items.forEach((el) => io.observe(el));

    /* Emniyet: gözlemci hiç tetiklenmezse içerik görünmez kalmasın. */
    const failsafe = window.setTimeout(
      () => items.forEach((el) => el.classList.add("in-focus")),
      2500
    );

    return () => {
      io.disconnect();
      window.clearTimeout(failsafe);
    };
  }, []);

  return null;
}
