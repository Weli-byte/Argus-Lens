"use client";

import { useRef, useEffect, useCallback, useState } from "react";

export type EyeCondition =
  | "normal"
  | "miyop"
  | "hipermetrop"
  | "astigmat"
  | "sasılık"
  | "deuteranopia"
  | "tritanopia"
  | "katarakt"
  | "glokom"
  | "makula"
  | "diyabetik"
  | "retinitis"
  | "presbiopi"
  | "ambliyopi"
  | "keratokonus"
  | "fotofobi"
  | "nistagmus"
  | "optikNorit"
  | "retinaDekolmani"
  | "hipertansif"
  | "uveit"
  | "leber";

interface Spot {
  x: number;
  y: number;
  r: number;
}

interface Floater {
  x: number;
  y: number;
  r: number;
  opacity: number;
  speed: number;
}

// panOffsetRef is a plain object ref — accept any ref shape that exposes { x, y }
type PanRef = { current: { x: number; y: number } | null | undefined };

export function useEyeFilter(
  videoRef: React.RefObject<HTMLVideoElement | null>,
  canvasRef: React.RefObject<HTMLCanvasElement | null>,
  panOffsetRef?: PanRef,
  /* Bolunmus karsilastirma icin TEMIZ kare katmani.
     Ayni kirpma/zoom/pan ile filtresiz cizilir. Ayri bir canvas kullanmanin
     sebebi: 6 durum `canvas.style.filter` (CSS filtresi) kullaniyor ve bu
     filtre canvas'in TAMAMINA uygulaniyor — ana canvas icinde bolme
     yapilsaydi saglikli taraf da bulaniklasirdi. */
  cleanCanvasRef?: React.RefObject<HTMLCanvasElement | null>
) {
  const [fps, setFps] = useState(0);
  const [isStreaming, setIsStreaming] = useState(false);

  const conditionRef  = useRef<EyeCondition>("normal");
  const zoomRef       = useRef<number>(1);
  /* Şiddet 0..1. Bulanık tabanlı durumlarda blur px değerini ölçekler,
     tüm durumlarda sağlıklı kare ile harmanlama oranını belirler.
     Varsayılan 0.6 = önceki sabit görünüme yakın. */
  const severityRef   = useRef<number>(0.6);
  const rafRef        = useRef<number>(0);
  const frameCountRef = useRef<number>(0);
  const fpsTimeRef    = useRef<number>(0);
  const spotsRef      = useRef<Spot[]>([]);
  const floatersRef   = useRef<Floater[]>([]);

  // ---------------------------------------------------------------------------
  // Core frame renderer — reassigned every render, read by loopRef every frame
  // ---------------------------------------------------------------------------

  const renderRef = useRef<() => void>(() => undefined);

  renderRef.current = () => {
    const video  = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.readyState < 2) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const w  = canvas.width;   // 1280
    const h  = canvas.height;  // 720
    const condition = conditionRef.current;
    const zoom      = zoomRef.current;
    const sev       = severityRef.current;
    /* Blur çarpanı: şiddet 0 → 0.22x, 1 → 1.65x. Kadranın ucundaki fark
       görülebilsin diye lineer değil, hafif genişletilmiş aralık. */
    const bl = (px: number) => `blur(${(px * (0.22 + sev * 1.43)).toFixed(2)}px)`;

    // ── Zoom crop ──────────────────────────────────────────────────────────
    const scale = 1 / zoom;
    const vw    = video.videoWidth  || w;
    const vh    = video.videoHeight || h;
    const sx0   = (vw * (1 - scale)) / 2;
    const sy0   = (vh * (1 - scale)) / 2;
    const sw    = vw * scale;
    const sh    = vh * scale;

    // ── Pan offset (screen-space → video-space) ────────────────────────────
    const panX = panOffsetRef?.current?.x ?? 0;
    const panY = panOffsetRef?.current?.y ?? 0;
    const pSx  = sw / w;   // video pixels per canvas pixel (x)
    const pSy  = sh / h;   // video pixels per canvas pixel (y)

    // Positive panOffset.x = image dragged right = viewing the LEFT part of video
    const finalSx = Math.max(0, Math.min(vw - sw, sx0 - panX * pSx));
    const finalSy = Math.max(0, Math.min(vh - sh, sy0 - panY * pSy));

    // ── Temiz kare katmani (bolunmus karsilastirma) ────────────────────────
    const clean = cleanCanvasRef?.current;
    if (clean) {
      const cctx = clean.getContext("2d");
      if (cctx) {
        cctx.filter = "none";
        cctx.globalAlpha = 1;
        cctx.clearRect(0, 0, clean.width, clean.height);
        cctx.drawImage(
          video, finalSx, finalSy, sw, sh, 0, 0, clean.width, clean.height
        );
      }
    }

    // ── Reset per-frame CSS/ctx state ──────────────────────────────────────
    canvas.style.filter = "none";
    ctx.filter          = "none";
    ctx.globalAlpha     = 1;
    ctx.clearRect(0, 0, w, h);

    // ── Condition switch ───────────────────────────────────────────────────
    switch (condition) {

      case "normal":
        ctx.drawImage(video, finalSx, finalSy, sw, sh, 0, 0, w, h);
        break;

      case "miyop": {
        ctx.filter = bl(7);
        ctx.drawImage(video, finalSx, finalSy, sw, sh, 0, 0, w, h);
        const r = Math.min(w, h) * 0.3;
        ctx.save();
        ctx.beginPath();
        ctx.arc(w / 2, h / 2, r, 0, Math.PI * 2);
        ctx.clip();
        ctx.filter = "none";
        ctx.drawImage(video, finalSx, finalSy, sw, sh, 0, 0, w, h);
        ctx.restore();
        break;
      }

      case "hipermetrop": {
        ctx.drawImage(video, finalSx, finalSy, sw, sh, 0, 0, w, h);
        const cr = Math.min(w, h) * 0.4;
        ctx.save();
        ctx.beginPath();
        ctx.arc(w / 2, h / 2, cr, 0, Math.PI * 2);
        ctx.clip();
        ctx.filter = bl(5);
        ctx.drawImage(video, finalSx, finalSy, sw, sh, 0, 0, w, h);
        ctx.restore();
        ctx.filter = "none";
        break;
      }

      case "astigmat": {
        ctx.filter      = bl(1.5);
        ctx.globalAlpha = 0.28;
        ctx.drawImage(video, finalSx, finalSy, sw, sh, -10, 0, w, h);
        ctx.drawImage(video, finalSx, finalSy, sw, sh,  10, 0, w, h);
        ctx.globalAlpha = 0.14;
        ctx.drawImage(video, finalSx, finalSy, sw, sh, -20, 0, w, h);
        ctx.drawImage(video, finalSx, finalSy, sw, sh,  20, 0, w, h);
        ctx.filter      = "none";
        ctx.globalAlpha = 0.72;
        ctx.drawImage(video, finalSx, finalSy, sw, sh, 0, 0, w, h);
        ctx.globalAlpha = 1;
        break;
      }

      case "sasılık": {
        ctx.drawImage(video, finalSx, finalSy, sw, sh, 0, 0, w, h);
        ctx.globalAlpha = 0.48;
        ctx.drawImage(video, finalSx, finalSy, sw, sh, 22, 10, w, h);
        ctx.globalAlpha = 1;
        break;
      }

      case "deuteranopia":
        canvas.style.filter = "url(#argus-deuteranopia)";
        ctx.drawImage(video, finalSx, finalSy, sw, sh, 0, 0, w, h);
        break;

      case "tritanopia":
        canvas.style.filter = "url(#argus-tritanopia)";
        ctx.drawImage(video, finalSx, finalSy, sw, sh, 0, 0, w, h);
        break;

      case "katarakt":
        canvas.style.filter = `${bl(2)} brightness(1.35) sepia(0.45) contrast(0.78)`;
        ctx.drawImage(video, finalSx, finalSy, sw, sh, 0, 0, w, h);
        break;

      case "glokom": {
        ctx.drawImage(video, finalSx, finalSy, sw, sh, 0, 0, w, h);
        const gG = ctx.createRadialGradient(w/2, h/2, h*0.19, w/2, h/2, h*0.72);
        gG.addColorStop(0,   "rgba(0,0,0,0)");
        gG.addColorStop(0.5, "rgba(0,0,0,0.72)");
        gG.addColorStop(1,   "rgba(0,0,0,1)");
        ctx.fillStyle = gG;
        ctx.fillRect(0, 0, w, h);
        break;
      }

      case "makula": {
        ctx.drawImage(video, finalSx, finalSy, sw, sh, 0, 0, w, h);
        ctx.save();
        ctx.translate(w / 2, h / 2);
        ctx.scale(1.55, 1);
        const mG = ctx.createRadialGradient(0, 0, 0, 0, 0, h * 0.14);
        mG.addColorStop(0,    "rgba(12,12,12,0.97)");
        mG.addColorStop(0.65, "rgba(12,12,12,0.85)");
        mG.addColorStop(1,    "rgba(12,12,12,0)");
        ctx.fillStyle = mG;
        ctx.beginPath();
        ctx.arc(0, 0, h * 0.16, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
        break;
      }

      case "diyabetik": {
        canvas.style.filter = bl(1);
        ctx.drawImage(video, finalSx, finalSy, sw, sh, 0, 0, w, h);
        if (spotsRef.current.length === 0) {
          spotsRef.current = Array.from({ length: 26 }, () => ({
            x: Math.random() * w,
            y: Math.random() * h,
            r: Math.random() * 20 + 5,
          }));
        }
        spotsRef.current.forEach(({ x, y, r }) => {
          const sg = ctx.createRadialGradient(x, y, 0, x, y, r);
          sg.addColorStop(0,   "rgba(18,0,0,0.9)");
          sg.addColorStop(0.6, "rgba(18,0,0,0.55)");
          sg.addColorStop(1,   "rgba(18,0,0,0)");
          ctx.fillStyle = sg;
          ctx.beginPath();
          ctx.arc(x, y, r, 0, Math.PI * 2);
          ctx.fill();
        });
        break;
      }

      case "retinitis": {
        ctx.drawImage(video, finalSx, finalSy, sw, sh, 0, 0, w, h);
        const rG = ctx.createRadialGradient(w/2, h/2, h*0.08, w/2, h/2, h*0.62);
        rG.addColorStop(0,    "rgba(0,0,0,0)");
        rG.addColorStop(0.32, "rgba(0,0,0,0.65)");
        rG.addColorStop(0.62, "rgba(0,0,0,0.97)");
        rG.addColorStop(1,    "rgba(0,0,0,1)");
        ctx.fillStyle = rG;
        ctx.fillRect(0, 0, w, h);
        ctx.globalAlpha = 0.75;
        for (let i = 0; i < 7; i++) {
          const px = Math.random() * w, py = Math.random() * h, pr = Math.random() * 2.5 + 0.5;
          ctx.fillStyle = `rgba(255,255,${Math.floor(Math.random()*80+170)},${(Math.random()*0.5+0.5).toFixed(2)})`;
          ctx.beginPath();
          ctx.arc(px, py, pr, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.globalAlpha = 1;
        break;
      }

      // ── NEW CONDITIONS ─────────────────────────────────────────────────────

      case "presbiopi": {
        // Sharp full frame; blur bottom 40% (near-vision / reading zone)
        ctx.drawImage(video, finalSx, finalSy, sw, sh, 0, 0, w, h);
        const blurY = h * 0.6;
        ctx.save();
        ctx.beginPath();
        ctx.rect(0, blurY, w, h - blurY);
        ctx.clip();
        ctx.filter = bl(5);
        ctx.drawImage(video, finalSx, finalSy, sw, sh, 0, 0, w, h);
        ctx.restore();
        ctx.filter = "none";
        break;
      }

      case "ambliyopi": {
        // Dominant (right) eye — full sharp frame
        ctx.drawImage(video, finalSx, finalSy, sw, sh, 0, 0, w, h);
        // Suppressed (left) eye — blurry + desaturated + dark
        ctx.save();
        ctx.beginPath();
        ctx.rect(0, 0, w / 2, h);
        ctx.clip();
        ctx.filter = `${bl(2.5)} saturate(0.25)`;
        ctx.drawImage(video, finalSx, finalSy, sw, sh, 0, 0, w, h);
        ctx.restore();
        ctx.filter = "none";
        ctx.fillStyle = "rgba(0,0,0,0.45)";
        ctx.fillRect(0, 0, w / 2, h);
        // Feathered divider
        const dg = ctx.createLinearGradient(w / 2 - 30, 0, w / 2 + 12, 0);
        dg.addColorStop(0, "rgba(0,0,0,0.45)");
        dg.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = dg;
        ctx.fillRect(w / 2 - 30, 0, 42, h);
        break;
      }

      case "keratokonus": {
        // Irregular cornea: animated ghost copies simulating halos + distortion
        canvas.style.filter = "contrast(1.1) brightness(1.05)";
        ctx.globalAlpha = 0.58;
        ctx.drawImage(video, finalSx, finalSy, sw, sh, 0, 0, w, h);
        const t = Date.now() * 0.0004;
        const ghosts = [
          { dx: Math.sin(t) * 7,       dy: Math.cos(t * 1.3) * 5,   a: 0.22 },
          { dx: Math.sin(t + 1) * 13,  dy: Math.cos(t + 0.5) * 8,   a: 0.13 },
          { dx: Math.sin(t + 2) * 18,  dy: Math.cos(t + 1.2) * 11,  a: 0.07 },
        ];
        ghosts.forEach(({ dx, dy, a }) => {
          const gsx = Math.max(0, Math.min(vw - sw, finalSx - dx * pSx));
          const gsy = Math.max(0, Math.min(vh - sh, finalSy - dy * pSy));
          ctx.globalAlpha = a;
          ctx.filter = bl(1);
          ctx.drawImage(video, gsx, gsy, sw, sh, 0, 0, w, h);
        });
        ctx.filter = "none";
        ctx.globalAlpha = 1;
        break;
      }

      case "fotofobi": {
        // Extreme light sensitivity: blown-out bright areas + white bloom
        canvas.style.filter = "brightness(1.8) contrast(1.4)";
        ctx.drawImage(video, finalSx, finalSy, sw, sh, 0, 0, w, h);
        const fG = ctx.createRadialGradient(w/2, h/2, 0, w/2, h/2, Math.min(w,h)*0.65);
        fG.addColorStop(0,   "rgba(255,255,255,0.32)");
        fG.addColorStop(0.5, "rgba(255,255,255,0.08)");
        fG.addColorStop(1,   "rgba(255,255,255,0)");
        ctx.fillStyle = fG;
        ctx.fillRect(0, 0, w, h);
        break;
      }

      case "nistagmus": {
        // Rhythmic involuntary oscillation of the eye
        const oscX = Math.sin(Date.now() * 0.008) * 14 * pSx;
        const oscY = Math.sin(Date.now() * 0.012) * 5  * pSy;
        const nsx  = Math.max(0, Math.min(vw - sw, finalSx + oscX));
        const nsy  = Math.max(0, Math.min(vh - sh, finalSy + oscY));
        ctx.drawImage(video, nsx, nsy, sw, sh, 0, 0, w, h);
        break;
      }

      case "optikNorit": {
        // Optic neuritis: large central scotoma + colour desaturation
        canvas.style.filter = `${bl(1)} saturate(0.38)`;
        ctx.drawImage(video, finalSx, finalSy, sw, sh, 0, 0, w, h);
        const oR = Math.min(w, h) * 0.28;
        const oG = ctx.createRadialGradient(w/2, h/2, 0, w/2, h/2, oR * 1.35);
        oG.addColorStop(0,    "rgba(8,8,8,0.97)");
        oG.addColorStop(0.65, "rgba(8,8,8,0.85)");
        oG.addColorStop(1,    "rgba(8,8,8,0)");
        ctx.fillStyle = oG;
        ctx.beginPath();
        ctx.arc(w / 2, h / 2, oR * 1.45, 0, Math.PI * 2);
        ctx.fill();
        break;
      }

      case "retinaDekolmani": {
        // Dark curtain falling from top + photopsia near curtain edge
        ctx.drawImage(video, finalSx, finalSy, sw, sh, 0, 0, w, h);
        const curtH = h * 0.42;
        const tm    = Date.now() * 0.0015;
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.lineTo(w, 0);
        ctx.lineTo(w, curtH + Math.sin(tm + w * 0.05) * 10);
        for (let x = w; x >= 0; x -= 8) {
          ctx.lineTo(x, curtH + Math.sin(tm + x * 0.04) * 10);
        }
        ctx.closePath();
        const cG = ctx.createLinearGradient(0, 0, 0, curtH + 20);
        cG.addColorStop(0,    "rgba(0,0,0,1)");
        cG.addColorStop(0.88, "rgba(0,0,0,0.95)");
        cG.addColorStop(1,    "rgba(0,0,0,0.85)");
        ctx.fillStyle = cG;
        ctx.fill();
        ctx.restore();
        // Photopsia near curtain boundary
        for (let i = 0; i < 5; i++) {
          if (Math.random() > 0.6) {
            const px = Math.random() * w;
            const py = curtH - 25 + Math.random() * 50;
            ctx.globalAlpha = Math.random() * 0.85 + 0.15;
            ctx.fillStyle   = "rgba(255,252,200,1)";
            ctx.beginPath();
            ctx.arc(px, py, Math.random() * 3 + 0.5, 0, Math.PI * 2);
            ctx.fill();
          }
        }
        ctx.globalAlpha = 1;
        break;
      }

      case "hipertansif": {
        // Hypertensive retinopathy: overall dimming + red vignette at edges
        canvas.style.filter = `${bl(1.5)} contrast(1.3) brightness(0.83)`;
        ctx.drawImage(video, finalSx, finalSy, sw, sh, 0, 0, w, h);
        const hG = ctx.createRadialGradient(w/2, h/2, h*0.32, w/2, h/2, h*0.82);
        hG.addColorStop(0, "rgba(140,0,0,0)");
        hG.addColorStop(1, "rgba(140,0,0,0.22)");
        ctx.fillStyle = hG;
        ctx.fillRect(0, 0, w, h);
        break;
      }

      case "uveit": {
        // Uveitis: overall haze + red tint + drifting floaters
        canvas.style.filter = `${bl(2)} brightness(0.9) contrast(0.85)`;
        ctx.drawImage(video, finalSx, finalSy, sw, sh, 0, 0, w, h);
        ctx.fillStyle = "rgba(180,55,55,0.1)";
        ctx.fillRect(0, 0, w, h);
        // Lazy-init floaters
        if (floatersRef.current.length === 0) {
          floatersRef.current = Array.from({ length: 7 }, () => ({
            x:       Math.random() * w,
            y:       Math.random() * h,
            r:       Math.random() * 6 + 2,
            opacity: Math.random() * 0.35 + 0.25,
            speed:   Math.random() * 0.28 + 0.08,
          }));
        }
        floatersRef.current.forEach((f) => {
          f.y += f.speed;
          if (f.y > h + f.r) f.y = -f.r;
          ctx.globalAlpha = f.opacity;
          ctx.fillStyle   = "rgba(16,6,6,0.88)";
          ctx.beginPath();
          ctx.arc(f.x, f.y, f.r, 0, Math.PI * 2);
          ctx.fill();
        });
        ctx.globalAlpha = 1;
        break;
      }

      case "leber": {
        // Leber CCA: severe congenital vision loss — shapes barely visible
        canvas.style.filter = `${bl(8)} contrast(0.5) brightness(0.65)`;
        ctx.drawImage(video, finalSx, finalSy, sw, sh, 0, 0, w, h);
        const lG = ctx.createRadialGradient(w/2, h/2, h*0.04, w/2, h/2, h*0.52);
        lG.addColorStop(0,    "rgba(0,0,0,0)");
        lG.addColorStop(0.28, "rgba(0,0,0,0.55)");
        lG.addColorStop(0.65, "rgba(0,0,0,0.93)");
        lG.addColorStop(1,    "rgba(0,0,0,1)");
        ctx.fillStyle = lG;
        ctx.fillRect(0, 0, w, h);
        break;
      }
    }

    /* ── Siddet harmanlamasi ───────────────────────────────────────
       Bulanik olmayan durumlar (renk korlugu, lekeler, tunel) blur
       olceklemesinden etkilenmiyor. Saglikli kareyi ustune dusuk alfayla
       cizmek 22 durumun hepsi icin surekli ve monoton bir kadran verir. */
    if (condition !== "normal" && sev < 1) {
      ctx.save();
      ctx.filter = "none";
      ctx.globalAlpha = (1 - sev) * 0.65;
      ctx.drawImage(video, finalSx, finalSy, sw, sh, 0, 0, w, h);
      ctx.restore();
      ctx.globalAlpha = 1;
    }

  };

  // ---------------------------------------------------------------------------
  // RAF loop — stable reference via loopRef pattern
  // ---------------------------------------------------------------------------

  const loopRef = useRef<((time: number) => void) | undefined>(undefined);

  loopRef.current = (time: number) => {
    frameCountRef.current++;
    if (time - fpsTimeRef.current >= 1000) {
      setFps(frameCountRef.current);
      frameCountRef.current = 0;
      fpsTimeRef.current    = time;
    }
    renderRef.current();
    rafRef.current = requestAnimationFrame((t) => loopRef.current!(t));
  };

  // ---------------------------------------------------------------------------
  // Public API
  // ---------------------------------------------------------------------------

  const startCamera = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } },
      });
      const video = videoRef.current;
      if (!video) return;
      video.srcObject = stream;
      await video.play();
      setIsStreaming(true);
      frameCountRef.current = 0;
      fpsTimeRef.current    = performance.now();
      rafRef.current        = requestAnimationFrame((t) => loopRef.current!(t));
    } catch (err) {
      console.error("Camera access denied:", err);
    }
  }, [videoRef]);

  const stopCamera = useCallback(() => {
    cancelAnimationFrame(rafRef.current);
    const video = videoRef.current;
    if (video?.srcObject) {
      (video.srcObject as MediaStream).getTracks().forEach((t) => t.stop());
      video.srcObject = null;
    }
    const canvas = canvasRef.current;
    if (canvas) {
      canvas.style.filter = "none";
      const ctx = canvas.getContext("2d");
      ctx?.clearRect(0, 0, canvas.width, canvas.height);
    }
    setIsStreaming(false);
    setFps(0);
    spotsRef.current   = [];
    floatersRef.current = [];
  }, [videoRef, canvasRef]);

  const setCondition = useCallback(
    (c: EyeCondition) => {
      conditionRef.current = c;
      const canvas = canvasRef.current;
      if (canvas) canvas.style.filter = "none";
      spotsRef.current   = [];
      floatersRef.current = [];
    },
    [canvasRef]
  );

  const setZoom = useCallback((z: number) => {
    zoomRef.current = z;
  }, []);

  /** Şiddet 0..1. UI kadranı bunu yüzde olarak gösterir. */
  const setSeverity = useCallback((v: number) => {
    severityRef.current = Math.max(0, Math.min(1, v));
  }, []);


  useEffect(() => {
    return () => { cancelAnimationFrame(rafRef.current); };
  }, []);

  return {
    fps,
    isStreaming,
    startCamera,
    stopCamera,
    setCondition,
    setZoom,
    setSeverity,
  };
}
