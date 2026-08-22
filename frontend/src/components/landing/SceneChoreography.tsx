"use client";

import { useLayoutEffect } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Lenis from "lenis";
import { lensProgress } from "@/lib/lens-progress";

/* ────────────────────────────────────────────────────────────────────────────
   SCROLL KOREOGRAFİSİ

   Beş sahne, tek anlatı hattı. Her hareketin bir sebebi var:

   01 GÖZ     hero pinlenir; scrub mercek elemanlarını patlatılmış optik
              diyagrama açar (lensProgress 0→1). Kamera içeri girer.
   02 TARAMA  namlu kadraja oturur — görüntü odağa gelir, HUD yazılır.
   03 TESPİT  ölçüm satırları sırayla yanar; her satır bir kanıt.
   04 YORUM   metin kolonu sabitlenirken görüntü kayar — okuma ile
              görüntü arasındaki gecikmeyi anlatır.
   05 AKSİYON diyafram kapanır, konsola devir.

   snap: yalnız 02-05 arası, yalnız fare/işaretçi cihazlarda. Dokunmatikte
   snap kullanıcıyla kavga eder; kapalı.
   prefers-reduced-motion: hiçbir ScrollTrigger kurulmaz, Lenis açılmaz,
   tüm içerik CSS tarafından zaten görünür durumdadır.
   ────────────────────────────────────────────────────────────────────────── */

export default function SceneChoreography() {
  useLayoutEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const root = document.documentElement;

    /* ── Reveal: odağa gelme. Hareket azaltmada CSS zaten görünür kılıyor. ── */
    // "boot" varyantı saf CSS ile çalışır (ilk ekran, JS beklemez) —
    // gözlemciye alınmaz.
    const targets = Array.from(
      document.querySelectorAll<HTMLElement>(
        '[data-reveal]:not([data-reveal="boot"])'
      )
    );
    let revealIO: IntersectionObserver | null = null;

    if (reduced) {
      targets.forEach((el) => el.classList.add("in-focus"));
      return;
    }

    revealIO = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("in-focus");
            revealIO?.unobserve(e.target);
          }
        });
      },
      // threshold DÜŞÜK olmak zorunda: [data-reveal="iris"] öğeleri
      // clip-path ile %8 genişliğe kırpılı başlıyor, 0.2 eşiği hiç dolmuyor.
      { threshold: 0.01, rootMargin: "0px 0px -14% 0px" }
    );
    targets.forEach((el) => revealIO?.observe(el));

    /* ── Lenis: eylemsizlikli kaydırma. GSAP ticker'ına bağlanır ki
         ScrollTrigger ile aynı karede güncellensin. ── */
    const lenis = new Lenis({
      duration: 1.05,
      smoothWheel: true,
      wheelMultiplier: 0.9,
      touchMultiplier: 1.4,
    });
    const raf = (time: number) => lenis.raf(time * 1000);
    lenis.on("scroll", ScrollTrigger.update);
    gsap.ticker.add(raf);
    gsap.ticker.lagSmoothing(0);

    gsap.registerPlugin(ScrollTrigger);

    const ctx = gsap.context(() => {
      /* 01 — hero: TEK pin'li zaman çizelgesi.
         Ayrı trigger'lar pin boşluğu yüzünden senkron kalmıyor ve hero
         eriyeceği yerde sert kenarla kesiliyordu. */
      const heroTl = gsap.timeline({
        scrollTrigger: {
          trigger: "#sahne-01",
          start: "top top",
          end: "+=115%",
          scrub: 0.55,
          pin: true,
          pinSpacing: true,
          invalidateOnRefresh: true,
        },
      });

      // Mercek yığını patlatılmış optik diyagrama açılır (0 → 1)
      heroTl.to(lensProgress, { value: 1, ease: "none", duration: 1 }, 0);

      // Metin odaktan çıkar — aşağı kaymaz, bulanıklaşır
      heroTl.to(
        "#sahne-01 .shell",
        { opacity: 0, filter: "blur(10px)", ease: "none", duration: 0.55 },
        0
      );

      // Son çeyrekte hero tamamen erir
      heroTl.to(
        "#sahne-01",
        { opacity: 0, ease: "none", duration: 0.3 },
        0.7
      );

      /* 02-05 — her sahnede görüntü odağa gelir (scale 1.06 → 1). */
      gsap.utils
        .toArray<HTMLElement>("[data-scene]:not([data-scene='01']) .barrel")
        .forEach((el) => {
          gsap.fromTo(
            el,
            { scale: 1.06 },
            {
              scale: 1,
              ease: "none",
              scrollTrigger: {
                trigger: el,
                start: "top bottom",
                end: "center center",
                scrub: 0.5,
              },
            }
          );
        });

      /* 04 — metin kolonu görüntüden geride kalır: okuma gecikmesi. */
      gsap.to("#sahne-04 dl", {
        yPercent: -14,
        ease: "none",
        scrollTrigger: {
          trigger: "#sahne-04",
          start: "top bottom",
          end: "bottom top",
          scrub: 0.8,
        },
      });

      /* Anamorfik çizgi sayfa boyunca iner — konumun tek göstergesi. */
      ScrollTrigger.create({
        start: 0,
        end: "max",
        onUpdate: (self) => {
          root.style.setProperty(
            "--streak-y",
            `${16 + self.progress * 66}%`
          );
        },
      });

      /* snap — yalnız hassas işaretçide, yalnız anlatı bloğunda */
      const fine = window.matchMedia("(pointer: fine)").matches;
      const narrative = document.querySelector<HTMLElement>("#anlati");
      if (fine && narrative) {
        const scenes = gsap.utils.toArray<HTMLElement>("#anlati [data-scene]");
        ScrollTrigger.create({
          trigger: narrative,
          start: "top top",
          end: "bottom bottom",
          snap: {
            snapTo: (progress, self) => {
              if (!self) return progress;
              const total = self.end - self.start;
              if (total <= 0) return progress;
              const points = scenes.map((s) => {
                const top = s.offsetTop - narrative.offsetTop;
                return gsap.utils.clamp(0, 1, top / total);
              });
              return gsap.utils.snap(points, progress);
            },
            duration: { min: 0.18, max: 0.5 },
            delay: 0.08,
            ease: "power2.inOut",
          },
        });
      }
    });

    /* ── İmleç paralaksı → 3D sahne. React state yok, doğrudan kanal. ── */
    const onPointer = (e: PointerEvent) => {
      lensProgress.px = (e.clientX / window.innerWidth) * 2 - 1;
      lensProgress.py = (e.clientY / window.innerHeight) * 2 - 1;
    };
    window.addEventListener("pointermove", onPointer, { passive: true });

    return () => {
      window.removeEventListener("pointermove", onPointer);
      revealIO?.disconnect();
      ctx.revert();
      gsap.ticker.remove(raf);
      lenis.destroy();
      ScrollTrigger.getAll().forEach((t) => t.kill());
    };
  }, []);

  return null;
}
