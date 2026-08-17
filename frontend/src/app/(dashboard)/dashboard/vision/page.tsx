"use client";

import React, {
  useRef,
  useState,
  useEffect,
  useCallback,
} from "react";
import { useRouter } from "next/navigation";
import {
  Camera,
  CameraOff,
  ZoomIn,
  Eye,
  Info,
  MessageSquare,
  Move,
  Download,
} from "lucide-react";
import { cn } from "@/lib/utils";
import ParticleField from "@/components/ui/ParticleField";
import { useEyeFilter, type EyeCondition } from "@/hooks/useEyeFilter";

// ---------------------------------------------------------------------------
// Condition catalogue (22 total)
// ---------------------------------------------------------------------------

interface ConditionMeta {
  id: EyeCondition;
  name: string;
  label: string;
  description: string;
  prevalence: string;
}

const CONDITIONS: ConditionMeta[] = [
  // ── Kırma Kusurları ──
  {
    id: "normal",
    name: "Normal",
    label: "Sağlıklı Göz",
    description:
      "Sağlıklı bir gözde ışık tam olarak retina üzerinde odaklanır. Uzak ve yakın nesneler eşit netlikte görünür, renk algısı tamdır.",
    prevalence: "Dünya nüfusunun yaklaşık %50'si.",
  },
  {
    id: "miyop",
    name: "Miyop",
    label: "Uzak Görememe",
    description:
      "Miyopi, gözün uzaktaki nesneleri net göremediği kırma kusurudur. Işık retina önünde odaklanır. Yakın nesneler net, uzak nesneler bulanık görünür.",
    prevalence: "Dünya nüfusunun yaklaşık %30'unda görülür.",
  },
  {
    id: "hipermetrop",
    name: "Hipermetrop",
    label: "Yakın Görememe",
    description:
      "Hipermetropi, gözün yakındaki nesneleri net göremediği kırma kusurudur. Işık retina arkasında odaklanır. Uzak nesneler görece net, yakındakiler bulanık görünür.",
    prevalence: "Dünya nüfusunun yaklaşık %25'inde görülür.",
  },
  {
    id: "astigmat",
    name: "Astigmat",
    label: "Astigmatizm",
    description:
      "Korneanın düzensiz eğriliğinden kaynaklanan bu kusurda görüntüler bulanık ya da çarpık görünür. Hem yakın hem uzak nesnelerde bozulma yaşanabilir.",
    prevalence: "Dünya nüfusunun yaklaşık %33'ünde görülür.",
  },
  {
    id: "presbiopi",
    name: "Presbiopi",
    label: "Yaşa Bağlı Yakın Görememe",
    description:
      "40 yaş sonrasında göz merceğinin esnekliğini kaybetmesiyle yakın mesafedeki nesneler bulanıklaşır. Okuma mesafesinde odaklanma güçleşir, uzak görüş etkilenmez.",
    prevalence: "Dünya nüfusunun yaklaşık %25'ini, 40 yaş üstünde çoğunluğu etkiler.",
  },
  // ── Göz Hareketleri ──
  {
    id: "sasılık",
    name: "Şaşılık",
    label: "Çift Görme (Diplopi)",
    description:
      "Strabismus veya şaşılıkta gözler farklı yönlere bakarak çift görme oluşturur. İki göz görüntüsü üst üste binmez; diplopi yani ikili imge meydana gelir.",
    prevalence: "Dünya nüfusunun yaklaşık %4'ünde görülür.",
  },
  {
    id: "nistagmus",
    name: "Nistagmus",
    label: "Göz Titremesi",
    description:
      "Gözlerin istemsiz, ritmik hareketi nedeniyle görüntü sürekli titrer veya kayar. Görme netliği düşer, baş dönmesi eşlik edebilir.",
    prevalence: "Yaklaşık 1.000 kişide 1-2'sinde görülür.",
  },
  {
    id: "ambliyopi",
    name: "Ambliyopi",
    label: "Tembel Göz",
    description:
      "Beyin, zayıf gözden gelen görüntüyü bastırır; o göz zamanla işlevini yitirir. Genellikle çocuklukta başlar, erken tedavi oldukça önemlidir.",
    prevalence: "Çocukların yaklaşık %2-3'ünde görülür.",
  },
  // ── Renk Görme ──
  {
    id: "deuteranopia",
    name: "Kırmızı-Yeşil Renk Körlüğü",
    label: "Deuteranopi",
    description:
      "Yeşil konları eksik olan kişilerde kırmızı ve yeşil renkler birbirinden ayırt edilemez. En sık rastlanan renk körlüğü türüdür.",
    prevalence: "Erkeklerin %8'ini, kadınların %0,5'ini etkiler.",
  },
  {
    id: "tritanopia",
    name: "Mavi-Sarı Renk Körlüğü",
    label: "Tritanopi",
    description:
      "Mavi konların yokluğuyla oluşan bu nadir renk körlüğünde mavi ve sarı renkler karışır. Gökyüzü yeşilimsi, sarı ise pembemsi görünebilir.",
    prevalence: "Dünya nüfusunun yaklaşık %0,01'inde görülür.",
  },
  // ── Kornea & Lens ──
  {
    id: "katarakt",
    name: "Katarakt",
    label: "Göz Merceği Bulanıklığı",
    description:
      "Katarakt, göz merceğinin zamanla bulanıklaşmasıyla oluşur. Görüntüler sisli ve sarımsı bir hal alır, kontrast duyarlılığı düşer.",
    prevalence: "60 yaş üstündeki bireylerin %50'sinden fazlasını etkiler.",
  },
  {
    id: "keratokonus",
    name: "Keratokonus",
    label: "Kornea Konus Şekli",
    description:
      "Korneanın incelerek konik şekil almasıyla ışık düzensiz kırılır. Işık kaynaklarının çevresinde hale ve ışın görülür; görüntüler hayalet izler oluşturur.",
    prevalence: "Yaklaşık 2.000 kişide 1'inde görülür.",
  },
  // ── Retina Hastalıkları ──
  {
    id: "glokom",
    name: "Glokom",
    label: "Tünel Görüşü",
    description:
      "Artmış göz içi basıncı görme sinirini hasarlandırarak periferik görmeyi yok eder. Sanki bir tünelin içinden bakıyormuş gibi yalnızca merkez net görünür.",
    prevalence: "Dünya nüfusunun yaklaşık %2'sinde görülür.",
  },
  {
    id: "makula",
    name: "Maküla Dejenerasyonu",
    label: "Merkezi Kör Alan",
    description:
      "Retinanın merkezi bölgesi (makula) hasar gördüğünde görüş alanının tam ortasında kör bir nokta oluşur. Periferik görme büyük ölçüde korunur.",
    prevalence: "50 yaş üstü bireylerin yaklaşık %8,7'sini etkiler.",
  },
  {
    id: "diyabetik",
    name: "Diyabetik Retinopati",
    label: "Kan Damarı Hasarı",
    description:
      "Diyabete bağlı retina kan damarları zedelendiğinde kanamalara bağlı koyu lekeler ve genel bir bulanıklık oluşur. İleri evrede görme tamamen kaybolabilir.",
    prevalence: "Diyabetli bireylerin yaklaşık %34'ünde görülür.",
  },
  {
    id: "retinitis",
    name: "Retinitis Pigmentosa",
    label: "Periferik Görme Kaybı",
    description:
      "Genetik kökenli bu hastalıkta retinanın çomak hücreleri ilerleyici biçimde tahrip olur. Periferik görme daralır, gece körlüğü ve fotopsi oluşur.",
    prevalence: "Dünya nüfusunun yaklaşık %0,04'ünü etkiler.",
  },
  {
    id: "retinaDekolmani",
    name: "Retina Dekolmanı",
    label: "Görüş Alanında Perde",
    description:
      "Retinanın yerinden ayrılmasıyla görüş alanında bir taraftan başlayan karanlık perde hissi oluşur. Yanıp sönen ışık parlamaları eşlik edebilir; acil müdahale gerektirir.",
    prevalence: "Yılda 10.000 kişide yaklaşık 1'inde görülür.",
  },
  {
    id: "leber",
    name: "Leber Konjenital Amorozisi",
    label: "Doğuştan Görme Kaybı",
    description:
      "Doğumsal retina distrofisi nedeniyle doğuştan ciddi görme azlığı ya da tam görme kaybı oluşur. Retina fotoalıcıları çalışmaz; yalnızca ışık-gölge farkı algılanabilir.",
    prevalence: "100.000 doğumda yaklaşık 2-3 vakada görülür.",
  },
  // ── Sinir & Damar ──
  {
    id: "optikNorit",
    name: "Optik Nörit",
    label: "Optik Sinir İltihabı",
    description:
      "Optik sinirin iltihaplanmasıyla görüş alanında merkezi kararma ve renk solgunluğu oluşur. Göz hareketi ile artan ağrı sık görülen belirtidir.",
    prevalence: "Yılda 100.000 kişide yaklaşık 5'inde görülür.",
  },
  {
    id: "hipertansif",
    name: "Hipertansif Retinopati",
    label: "Tansiyon Kaynaklı Retina Hasarı",
    description:
      "Yüksek tansiyon retina kan damarlarını daraltarak görüşü bozar. Kenar bölgelerde kırmızımsı vasküler hasar belirtileri ve genel bulanıklık oluşur.",
    prevalence: "Hipertansif bireylerin yaklaşık %70'inde bulgu görülür.",
  },
  {
    id: "uveit",
    name: "Üveit",
    label: "Göz İçi İltihap",
    description:
      "Gözün orta tabakasının (uvea) iltihaplanmasıyla görüş bulanır, ışığa duyarlılık artar. Hafif yüzen lekeler (floaters) görüntüde belirginleşir.",
    prevalence: "Görme kaybının %10-15'inden sorumludur.",
  },
  {
    id: "fotofobi",
    name: "Fotofobi",
    label: "Işık Hassasiyeti",
    description:
      "Işığa aşırı duyarlılık nedeniyle parlak ortamlarda şiddetli rahatsızlık ve görme bozukluğu yaşanır. Mümkün olan en parlak noktalar aşırı beyaz ve kamaştırıcı görünür.",
    prevalence: "Kronik migren hastalarının %80'inde, pek çok göz hastalığına eşlik eder.",
  },
];

interface ConditionGroup {
  label: string;
  ids: EyeCondition[];
}

const GROUPS: ConditionGroup[] = [
  { label: "Kırma Kusurları",    ids: ["normal","miyop","hipermetrop","astigmat","presbiopi"] },
  { label: "Göz Hareketleri",    ids: ["sasılık","nistagmus","ambliyopi"] },
  { label: "Renk Görme",         ids: ["deuteranopia","tritanopia"] },
  { label: "Kornea & Lens",      ids: ["katarakt","keratokonus"] },
  { label: "Retina Hastalıkları",ids: ["glokom","makula","diyabetik","retinitis","retinaDekolmani","leber"] },
  { label: "Sinir & Damar",      ids: ["optikNorit","hipertansif","uveit","fotofobi"] },
];

const ZOOM_LEVELS = [1, 2, 4, 8, 10] as const;
type ZoomLevel = (typeof ZOOM_LEVELS)[number];

// 20 floating idle dots — deterministic positions (avoids SSR hydration mismatch)
const IDLE_DOTS = Array.from({ length: 20 }, (_, i) => ({
  left: `${(i * 37 + 11) % 100}%`,
  top: `${(i * 53 + 23) % 100}%`,
  duration: 2 + (i % 5) * 0.5,
  delay: (i % 7) * 0.45,
}));

// Canvas logical dimensions (matches canvas width/height attributes)
const CANVAS_W = 1280;
const CANVAS_H = 720;

// ---------------------------------------------------------------------------
// SVG colour-blindness filter definitions
// ---------------------------------------------------------------------------

function SvgFilters() {
  return (
    <svg
      aria-hidden="true"
      style={{ position: "absolute", width: 0, height: 0, overflow: "hidden" }}
    >
      <defs>
        <filter id="argus-deuteranopia" colorInterpolationFilters="sRGB">
          <feColorMatrix type="matrix"
            values="0.625 0.375 0   0 0
                    0.7   0.3   0   0 0
                    0     0.3   0.7 0 0
                    0     0     0   1 0" />
        </filter>
        <filter id="argus-tritanopia" colorInterpolationFilters="sRGB">
          <feColorMatrix type="matrix"
            values="0.95  0.05  0     0 0
                    0     0.433 0.567 0 0
                    0     0.475 0.525 0 0
                    0     0     0     1 0" />
        </filter>
      </defs>
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Minimap: shows current viewport position within the full frame
// ---------------------------------------------------------------------------

function Minimap({
  zoom,
  panX,
  panY,
}: {
  zoom: number;
  panX: number;
  panY: number;
}) {
  if (zoom <= 1) return null;

  const vpW = 80 / zoom;
  const vpH = 60 / zoom;
  // User's specified formula
  const rx = (40 - vpW / 2) - (panX / CANVAS_W) * 80 / zoom;
  const ry = (30 - vpH / 2) - (panY / CANVAS_H) * 60 / zoom;
  const clampedRx = Math.max(0, Math.min(80 - vpW, rx));
  const clampedRy = Math.max(0, Math.min(60 - vpH, ry));

  return (
    <div
      className="absolute bottom-10 right-3 rounded border border-slate-600/60 bg-black/70 overflow-hidden"
      style={{ width: 80, height: 60 }}
      title="Görüntü konumu"
    >
      {/* Full-frame background */}
      <div className="absolute inset-0 border border-slate-700/40" />
      {/* Viewport indicator */}
      <div
        className="absolute border border-[#00D4FF] bg-[#00D4FF]/10 rounded-sm"
        style={{
          left:   clampedRx,
          top:    clampedRy,
          width:  vpW,
          height: vpH,
        }}
      />
      {/* Label */}
      <span className="absolute bottom-0.5 left-1 text-[7px] font-mono text-slate-500 uppercase">
        nav
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function CameraPage() {
  const router   = useRouter();
  const videoRef  = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Pan offset: state (for UI re-render) + ref (read directly by RAF loop)
  const panOffsetRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const [panOffset,     setPanOffset]     = useState({ x: 0, y: 0 });
  const [isDragging,    setIsDragging]    = useState(false);
  const [dragStart,     setDragStart]     = useState({ x: 0, y: 0 });
  const [lastPanOffset, setLastPanOffset] = useState({ x: 0, y: 0 });

  const [activeCondition, setActiveCondition] = useState<EyeCondition>("normal");
  const [activeZoom,      setActiveZoom]      = useState<ZoomLevel>(1);
  const [showPanHint,     setShowPanHint]     = useState(false);
  const hintShownRef = useRef(false);

  const { fps, isStreaming, startCamera, stopCamera, setCondition, setZoom } =
    useEyeFilter(videoRef, canvasRef, panOffsetRef);

  const activeMeta = CONDITIONS.find((c) => c.id === activeCondition) ?? CONDITIONS[0];

  // ── Reset pan when zoom returns to 1× ────────────────────────────────────
  useEffect(() => {
    if (activeZoom === 1) {
      const zero = { x: 0, y: 0 };
      setPanOffset(zero);
      setLastPanOffset(zero);
      panOffsetRef.current = zero;
    }
  }, [activeZoom]);

  // ── Handlers ─────────────────────────────────────────────────────────────

  const handleCondition = useCallback(
    (id: EyeCondition) => {
      setActiveCondition(id);
      setCondition(id);
    },
    [setCondition]
  );

  const handleZoom = useCallback(
    (z: ZoomLevel) => {
      setActiveZoom(z);
      setZoom(z);
      if (z > 1 && !hintShownRef.current) {
        hintShownRef.current = true;
        setShowPanHint(true);
        setTimeout(() => setShowPanHint(false), 2200);
      }
    },
    [setZoom]
  );

  // Screenshot: current canvas frame as PNG download (client-side only)
  const handleScreenshot = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const link = document.createElement("a");
    link.download = `arguslens-${Date.now()}.png`;
    link.href = canvas.toDataURL("image/png");
    link.click();
  }, []);

  // Mouse
  const handleMouseDown = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (activeZoom <= 1) return;
      setIsDragging(true);
      setDragStart({ x: e.clientX - lastPanOffset.x, y: e.clientY - lastPanOffset.y });
    },
    [activeZoom, lastPanOffset]
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (!isDragging) return;
      const maxPX = CANVAS_W * (1 - 1 / activeZoom) / 2;
      const maxPY = CANVAS_H * (1 - 1 / activeZoom) / 2;
      const nx = Math.max(-maxPX, Math.min(maxPX, e.clientX - dragStart.x));
      const ny = Math.max(-maxPY, Math.min(maxPY, e.clientY - dragStart.y));
      const next = { x: nx, y: ny };
      setPanOffset(next);
      panOffsetRef.current = next;
    },
    [isDragging, dragStart, activeZoom]
  );

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
    setLastPanOffset(panOffset);
  }, [panOffset]);

  const handleMouseLeave = useCallback(() => {
    if (isDragging) {
      setIsDragging(false);
      setLastPanOffset(panOffset);
    }
  }, [isDragging, panOffset]);

  // Touch
  const handleTouchStart = useCallback(
    (e: React.TouchEvent<HTMLCanvasElement>) => {
      if (activeZoom <= 1) return;
      const t = e.touches[0];
      setIsDragging(true);
      setDragStart({ x: t.clientX - lastPanOffset.x, y: t.clientY - lastPanOffset.y });
    },
    [activeZoom, lastPanOffset]
  );

  const handleTouchMove = useCallback(
    (e: React.TouchEvent<HTMLCanvasElement>) => {
      if (!isDragging) return;
      e.preventDefault();
      const t = e.touches[0];
      const maxPX = CANVAS_W * (1 - 1 / activeZoom) / 2;
      const maxPY = CANVAS_H * (1 - 1 / activeZoom) / 2;
      const nx = Math.max(-maxPX, Math.min(maxPX, t.clientX - dragStart.x));
      const ny = Math.max(-maxPY, Math.min(maxPY, t.clientY - dragStart.y));
      const next = { x: nx, y: ny };
      setPanOffset(next);
      panOffsetRef.current = next;
    },
    [isDragging, dragStart, activeZoom]
  );

  const handleTouchEnd = useCallback(() => {
    setIsDragging(false);
    setLastPanOffset(panOffset);
  }, [panOffset]);

  useEffect(() => {
    return () => { stopCamera(); };
  }, [stopCamera]);

  const hasPan   = panOffset.x !== 0 || panOffset.y !== 0;
  const cursorStyle: React.CSSProperties =
    activeZoom > 1
      ? { cursor: isDragging ? "grabbing" : "grab" }
      : { cursor: "default" };

  // ─────────────────────────────────────────────────────────────────────────

  return (
    <>
      <SvgFilters />
      <video ref={videoRef} playsInline muted className="hidden" aria-hidden="true" />

      {/* ================================================================== */}
      {/* Full-height layout: page header + split                             */}
      {/* ================================================================== */}
      <div
        className="flex flex-col gap-4 overflow-hidden"
        style={{ height: "calc(100vh - 57px - 48px)" }}
      >
        {/* Page header */}
        <div className="shrink-0">
          <p className="text-[11px] text-slate-500 tracking-wide">
            ArgusLens <span className="text-slate-700">/</span>{" "}
            <span className="text-cyan-400 font-medium">Kamera</span>
          </p>
          <h1 className="text-3xl font-black text-white tracking-tight mt-1">
            CANLI GÖRÜNTÜ
          </h1>
          <div className="w-14 h-0.5 bg-cyan-400 rounded-full mt-2" />
        </div>

        <div className="flex gap-4 flex-1 min-h-0 overflow-hidden">
        {/* ================================================================ */}
        {/* LEFT — camera canvas (70%)                                       */}
        {/* ================================================================ */}
        <div className="flex flex-col flex-[7] min-w-0">

          {/* Canvas viewport */}
          <div className="relative flex-1 rounded-[20px] border-2 border-[rgba(0,212,255,0.2)] bg-black overflow-hidden min-h-0">

            <canvas
              ref={canvasRef}
              width={CANVAS_W}
              height={CANVAS_H}
              className="w-full h-full object-contain"
              style={cursorStyle}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              onMouseLeave={handleMouseLeave}
              onTouchStart={handleTouchStart}
              onTouchMove={handleTouchMove}
              onTouchEnd={handleTouchEnd}
            />

            {/* Idle placeholder — particles + blinking eye + start button */}
            {!isStreaming && (
              <div className="absolute inset-0 bg-black flex flex-col items-center justify-center gap-8 overflow-hidden">
                <ParticleField density={48} className="absolute inset-0 w-full h-full" />
                {/* Floating dots */}
                {IDLE_DOTS.map((d, i) => (
                  <span
                    key={i}
                    className="absolute rounded-full"
                    style={{
                      left: d.left,
                      top: d.top,
                      width: 3,
                      height: 3,
                      background: "#00D4FF",
                      opacity: 0,
                      animation: `floatDot ${d.duration}s ease-in-out ${d.delay}s infinite`,
                    }}
                  />
                ))}
                {/* Idle scan line */}
                <div
                  className="absolute left-0 w-full"
                  style={{
                    height: 1,
                    background:
                      "linear-gradient(90deg, transparent, rgba(0,212,255,0.4), transparent)",
                    animation: "scanY 4s ease-in-out infinite",
                  }}
                />
                <div className="absolute size-[420px] rounded-full border border-cyan-500/10" />
                <div className="absolute size-[320px] rounded-full border border-cyan-500/15 animate-[ring-pulse_3.5s_ease-out_infinite]" />
                <div className="absolute size-[320px] rounded-full border border-dashed border-cyan-500/15 animate-[spin_30s_linear_infinite]" />
                <svg
                  viewBox="0 0 120 80"
                  className="relative w-44 animate-[blink_4s_ease-in-out_infinite] drop-shadow-[0_0_30px_rgba(0,212,255,0.3)]"
                  style={{ transformOrigin: "60px 40px" }}
                >
                  <path
                    d="M8 40 Q60 4 112 40 Q60 76 8 40 Z"
                    fill="none"
                    stroke="#00D4FF"
                    strokeOpacity="0.5"
                    strokeWidth="2"
                  />
                  <circle
                    cx="60"
                    cy="40"
                    r="16"
                    fill="rgba(0,212,255,0.08)"
                    stroke="#00D4FF"
                    strokeWidth="2"
                  />
                  <circle cx="60" cy="40" r="7" fill="#00D4FF" />
                  <circle cx="63" cy="37" r="2" fill="#F8FAFC" opacity="0.85" />
                </svg>
                <button
                  onClick={startCamera}
                  className="relative flex items-center gap-2.5 h-12 px-10 rounded-xl bg-gradient-to-r from-cyan-500 to-sky-500 text-[#080B0F] text-sm font-bold tracking-wide transition-all duration-300 hover:shadow-[0_0_32px_rgba(0,212,255,0.5)] hover:scale-105 active:scale-95"
                >
                  <Camera className="size-4.5" />
                  Kamerayı Başlat
                </button>
              </div>
            )}

            {isStreaming && (
              <>
                {/* HUD corner brackets */}
                <div className="pointer-events-none absolute inset-4">
                  <span className="absolute left-0 top-0 size-10 border-l-2 border-t-2 border-cyan-400/50 rounded-tl-lg" />
                  <span className="absolute right-0 top-0 size-10 border-r-2 border-t-2 border-cyan-400/50 rounded-tr-lg" />
                  <span className="absolute left-0 bottom-0 size-10 border-l-2 border-b-2 border-cyan-400/50 rounded-bl-lg" />
                  <span className="absolute right-0 bottom-0 size-10 border-r-2 border-b-2 border-cyan-400/50 rounded-br-lg" />
                </div>

                {/* CANLI + FPS + pan — top-left */}
                <div className="absolute top-5 left-5 flex items-center gap-2">
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-black/70 border border-cyan-500/40 font-mono text-[11px] font-bold tracking-widest text-cyan-400 shadow-[0_0_12px_rgba(0,212,255,0.2)]">
                    <span className="size-1.5 rounded-full bg-cyan-400 animate-pulse" />
                    CANLI
                  </span>
                  <span className="px-2 py-0.5 rounded bg-black/60 font-mono text-[11px] text-cyan-400">
                    {fps} fps
                  </span>
                  {/* Pan position indicator */}
                  {activeZoom > 1 && hasPan && (
                    <span className="px-2 py-0.5 rounded bg-black/60 font-mono text-[10px] text-cyan-400 flex items-center gap-1">
                      <Move className="size-2.5" />
                      X{panOffset.x > 0 ? "+" : ""}{Math.round(panOffset.x)}{" "}
                      Y{panOffset.y > 0 ? "+" : ""}{Math.round(panOffset.y)}
                    </span>
                  )}
                </div>

                {/* Active condition label */}
                <div className="absolute bottom-20 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-black/70 border border-[rgba(0,212,255,0.2)] font-mono text-[11px] text-slate-200 whitespace-nowrap">
                  {activeMeta.name}
                  <span className="ml-2 text-slate-500">— {activeMeta.label}</span>
                </div>

                {/* Bottom control bar */}
                <div className="absolute bottom-0 inset-x-0 flex items-center justify-center gap-3 px-5 py-4 bg-gradient-to-t from-black/85 via-black/40 to-transparent">
                  <button
                    onClick={stopCamera}
                    className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-red-500/15 border border-red-500/40 text-red-400 text-xs font-bold tracking-wide transition-all duration-300 hover:bg-red-500/25 hover:shadow-[0_0_16px_rgba(239,68,68,0.25)]"
                  >
                    <CameraOff className="size-4" />
                    Durdur
                  </button>
                  <button
                    onClick={handleScreenshot}
                    className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-cyan-500/10 border border-cyan-500/40 text-cyan-400 text-xs font-bold tracking-wide transition-all duration-300 hover:bg-cyan-500/20 hover:shadow-[0_0_16px_rgba(0,212,255,0.25)]"
                  >
                    <Download className="size-4" />
                    Ekran Görüntüsü
                  </button>
                </div>
              </>
            )}

            {/* Zoom badge — top-right */}
            <div className="absolute top-5 right-5 px-2.5 py-1 rounded-full bg-black/70 border border-cyan-500/30 font-mono text-[11px] font-bold text-cyan-400 flex items-center gap-1">
              <ZoomIn className="size-3" />
              {activeZoom}×
            </div>

            {/* Minimap */}
            <Minimap zoom={activeZoom} panX={panOffset.x} panY={panOffset.y} />

            {/* Pan hint tooltip */}
            {showPanHint && (
              <div className="absolute bottom-24 left-1/2 -translate-x-1/2 px-3 py-1.5 rounded-lg bg-[#00D4FF]/15 border border-[#00D4FF]/40 font-mono text-[11px] text-[#00D4FF] whitespace-nowrap animate-fade-in">
                Görüntüyü keşfetmek için sürükleyin
              </div>
            )}
          </div>
        </div>

        {/* ================================================================ */}
        {/* RIGHT — controls (30%)                                           */}
        {/* ================================================================ */}
        <div className="flex-[3] flex flex-col gap-4 overflow-y-auto min-w-0">

          {/* ── Zoom ─────────────────────────────────────────────────────── */}
          <div className="card-lift rounded-2xl border border-[rgba(0,212,255,0.12)] bg-gradient-to-br from-[#0D1117] to-[#111827] p-4 space-y-3 shrink-0">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest flex items-center gap-1.5">
              <ZoomIn className="size-3.5 text-cyan-400" /> Yaklaştırma
            </p>
            <div className="grid grid-cols-5 gap-2">
              {ZOOM_LEVELS.map((z) => (
                <button
                  key={z}
                  onClick={() => handleZoom(z)}
                  className={cn(
                    "aspect-square rounded-lg text-xs font-mono transition-all duration-300 border",
                    activeZoom === z
                      ? "bg-cyan-500 text-black font-bold border-cyan-500 shadow-[0_0_12px_rgba(0,212,255,0.35)]"
                      : "bg-transparent border-slate-700 text-slate-400 hover:border-cyan-500 hover:text-cyan-400"
                  )}
                >
                  {z}×
                </button>
              ))}
            </div>
            {activeZoom > 1 && (
              <p className="text-[10px] font-mono text-slate-600 flex items-center gap-1">
                <Move className="size-2.5 text-cyan-600" />
                Görüntüyü taşımak için sürükleyin
              </p>
            )}
          </div>

          {/* ── Eye conditions (grouped) ──────────────────────────────────── */}
          <div className="card-lift rounded-2xl border border-[rgba(0,212,255,0.12)] bg-gradient-to-br from-[#0D1117] to-[#111827] p-4 space-y-3">
            <div>
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest flex items-center gap-1.5">
                <Eye className="size-3.5 text-cyan-400" /> Göz Durumu
              </p>
              <p className="text-[10px] text-slate-600 mt-0.5">
                Bir göz hastalığı seçin
              </p>
            </div>

            <div className="space-y-4 max-h-[52vh] overflow-y-auto pr-0.5">
              {GROUPS.map((group, gi) => {
                const groupConditions = group.ids
                  .map((id) => CONDITIONS.find((c) => c.id === id))
                  .filter(Boolean) as ConditionMeta[];

                return (
                  <div
                    key={group.label}
                    className={cn(
                      gi > 0 && "border-t border-[rgba(255,255,255,0.06)] pt-3"
                    )}
                  >
                    <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">
                      {group.label}
                    </p>

                    <div className="space-y-1.5">
                      {groupConditions.map((cond) => (
                        <button
                          key={cond.id}
                          onClick={() => handleCondition(cond.id)}
                          className={cn(
                            "w-full text-left py-3 px-4 rounded-[10px] border transition-all duration-300",
                            activeCondition === cond.id
                              ? "border-cyan-500 bg-cyan-500/10 shadow-[0_0_10px_rgba(0,212,255,0.08)]"
                              : "border-[rgba(255,255,255,0.06)] hover:border-slate-600 hover:bg-slate-800/50"
                          )}
                        >
                          <div className="flex items-center justify-between">
                            <p className={cn(
                              "text-sm font-semibold",
                              activeCondition === cond.id ? "text-cyan-400" : "text-slate-200"
                            )}>
                              {cond.name}
                            </p>
                            {activeCondition === cond.id && (
                              <span className="size-1.5 rounded-full bg-cyan-400 shrink-0" />
                            )}
                          </div>
                          <p className="text-xs text-slate-500 mt-0.5 leading-tight">
                            {cond.label}
                          </p>
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* ── Info panel ──────────────────────────────────────────────── */}
          <div className="rounded-r-xl border-l-2 border-cyan-500 bg-cyan-500/5 p-4 space-y-3 shrink-0">
            <div className="flex items-center gap-1.5">
              <Info className="size-3.5 text-cyan-400" />
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest">
                Bilgi
              </p>
            </div>
            <div className="space-y-2">
              <p className="text-sm text-cyan-400 font-bold">
                {activeMeta.name}
              </p>
              <p className="text-xs text-slate-400 leading-relaxed">
                {activeMeta.description}
              </p>
              <div className="flex items-start gap-1.5 pt-2 border-t border-[rgba(0,212,255,0.15)]">
                <span className="text-[9px] text-slate-500 uppercase tracking-wider shrink-0 mt-0.5">
                  Görülme Oranı
                </span>
                <span className="text-[11px] text-amber-400">
                  {activeMeta.prevalence}
                </span>
              </div>
            </div>

            {/* AI'a sor button */}
            <button
              onClick={() =>
                router.push(
                  `/dashboard/chat?q=${encodeURIComponent(
                    `${activeMeta.name} göz hastalığı hakkında bilgi ver. Belirtileri, nedenleri ve tedavisi nelerdir?`
                  )}`
                )
              }
              className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg border border-cyan-500/20 bg-[#080B0F]/60 text-xs font-semibold text-slate-400 hover:border-cyan-500/50 hover:text-cyan-400 transition-all duration-300"
            >
              <MessageSquare className="size-3.5" />
              Bu hastalık hakkında AI&apos;a sor
            </button>
          </div>
        </div>
        </div>
      </div>
    </>
  );
}
