"use client";

import React, {
  useRef,
  useState,
  useEffect,
  useCallback,
  useMemo,
} from "react";
import { useRouter } from "next/navigation";
import {
  CameraOff,
  Columns2,
  SlidersHorizontal,
  ZoomIn,
  Eye,
  Info,
  MessageSquare,
  Move,
  Download,
} from "lucide-react";
import CameraIdleStage from "@/components/vision/CameraIdleStage";
import ConditionPicker, {
  type PickerItem,
} from "@/components/vision/ConditionPicker";
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
  const t = useT();
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
      title={t("Görüntü konumu")}
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
import { useLocale, useT, pct } from "@/lib/i18n";

export default function CameraPage() {
  const { t, locale } = useLocale();
  const router   = useRouter();
  const videoRef  = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Pan offset: state (for UI re-render) + ref (read directly by RAF loop)
  const panOffsetRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const [panOffset,     setPanOffset]     = useState({ x: 0, y: 0 });
  const [isDragging,    setIsDragging]    = useState(false);
  const [dragStart,     setDragStart]     = useState({ x: 0, y: 0 });
  const [lastPanOffset, setLastPanOffset] = useState({ x: 0, y: 0 });

  const cleanCanvasRef = useRef<HTMLCanvasElement>(null);
  /* Şiddet 0..1 ve bölünmüş karşılaştırma ayırıcı konumu 0..1 (null = kapalı) */
  const [severity, setSeverityState] = useState(0.6);
  const [split, setSplit] = useState<number | null>(null);
  const [shifting, setShifting] = useState(false);

  const [activeCondition, setActiveCondition] = useState<EyeCondition>("normal");
  const [activeZoom,      setActiveZoom]      = useState<ZoomLevel>(1);
  const [showPanHint,     setShowPanHint]     = useState(false);
  const hintShownRef = useRef(false);

  const {
    fps,
    isStreaming,
    startCamera,
    stopCamera,
    setCondition,
    setZoom,
    setSeverity,
  } =
    useEyeFilter(videoRef, canvasRef, panOffsetRef, cleanCanvasRef);

  const activeMeta = CONDITIONS.find((c) => c.id === activeCondition) ?? CONDITIONS[0];

  const changeSeverity = useCallback(
    (v: number) => {
      setSeverityState(v);
      setSeverity(v);
    },
    [setSeverity]
  );

  const pickerItems: PickerItem[] = useMemo(
    () =>
      GROUPS.flatMap((g) =>
        g.ids
          .map((id) => CONDITIONS.find((c) => c.id === id))
          .filter(Boolean)
          .map((c) => ({
            id: (c as ConditionMeta).id,
            name: t((c as ConditionMeta).name),
            label: t((c as ConditionMeta).label),
            group: t(g.label),
          }))
      ),
    [t]
  );

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

  /* Durum değişince kare ~400 ms odak kaydırır: eski filtre bulanıklaşır,
     yenisi nete gelir. Anında zıplamak "alet ayarlanıyor" hissini bozuyordu.
     Efekt yerine olay işleyicisinde tetiklenir — efekt gövdesinde senkron
     setState zincirleme render uyarısı veriyordu. */
  const shiftTimer = useRef<number | null>(null);
  const triggerShift = useCallback(() => {
    if (shiftTimer.current !== null) window.clearTimeout(shiftTimer.current);
    setShifting(true);
    shiftTimer.current = window.setTimeout(() => setShifting(false), 420);
  }, []);

  const handleCondition = useCallback(
    (id: EyeCondition) => {
      setActiveCondition(id);
      setCondition(id);
      triggerShift();
    },
    [setCondition, triggerShift]
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
          <p className="t-dial">
            ArgusLens <span className="text-[var(--ink-faint)]">/</span>{" "}
            <span className="text-[var(--ink-title)]">{t("Kamera")}</span>
          </p>
          <h1 className="t-display-sm mt-1" style={{ fontSize: "var(--p-text-xl)" }}>
            {t("CANLI")} <span className="t-counter">{t("görüntü")}</span>
          </h1>
          <div className="mt-2 h-px w-14 bg-[var(--accent-status)]" />
        </div>

        <div className="flex gap-4 flex-1 min-h-0 overflow-hidden">
        {/* ================================================================ */}
        {/* LEFT — camera canvas (70%)                                       */}
        {/* ================================================================ */}
        <div className="flex flex-col flex-[7] min-w-0">

          {/* Canvas viewport */}
          <div className="vis-stage flex-1 min-h-0">

            <canvas
              ref={canvasRef}
              data-shift={shifting ? "true" : undefined}
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

            {/* Bekleme: kapali vizor. Zemin video + fare/tekerlek paralaksi. */}
            {!isStreaming && <CameraIdleStage onStart={startCamera} />}

            {/* Bölünmüş karşılaştırma: SOL taraf sağlıklı göz.
                Ayrı canvas kullanılıyor çünkü 6 durum canvas.style.filter
                (CSS filtresi) uyguluyor ve o filtre canvas'in tamamını
                etkiliyor — ana canvas içinde bölünseydi sağlıklı taraf da
                bulanıklaşırdı. */}
            {isStreaming && split !== null && activeCondition !== "normal" && (
              <>
                <canvas
                  ref={cleanCanvasRef}
                  width={CANVAS_W}
                  height={CANVAS_H}
                  aria-hidden="true"
                  className="pointer-events-none absolute inset-0 h-full w-full object-contain"
                  style={{ clipPath: `inset(0 ${(1 - split) * 100}% 0 0)` }}
                />
                <div
                  className="vis-split-handle"
                  style={{ left: `${split * 100}%` }}
                  role="slider"
                  tabIndex={0}
                  aria-label={t("Karşılaştırma ayırıcı")}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={Math.round(split * 100)}
                  onKeyDown={(e) => {
                    if (e.key === "ArrowLeft")
                      setSplit((v) => Math.max(0, (v ?? 0.5) - 0.04));
                    if (e.key === "ArrowRight")
                      setSplit((v) => Math.min(1, (v ?? 0.5) + 0.04));
                  }}
                  onPointerDown={(e) => {
                    e.currentTarget.setPointerCapture(e.pointerId);
                    const box = (
                      e.currentTarget.parentElement as HTMLElement
                    ).getBoundingClientRect();
                    const move = (ev: PointerEvent) => {
                      setSplit(
                        Math.max(0, Math.min(1, (ev.clientX - box.left) / box.width))
                      );
                    };
                    const up = () => {
                      window.removeEventListener("pointermove", move);
                      window.removeEventListener("pointerup", up);
                    };
                    window.addEventListener("pointermove", move);
                    window.addEventListener("pointerup", up);
                  }}
                >
                  <span className="vis-split-grip" />
                  <span className="vis-split-tag vis-split-tag-l">{t("SAĞLIKLI")}</span>
                  <span className="vis-split-tag vis-split-tag-r">
                    {t(activeMeta.name).toLocaleUpperCase(locale)}
                  </span>
                </div>
              </>
            )}

            {isStreaming && (
              <>
                {/* HUD corner brackets */}
                <div className="pointer-events-none absolute inset-4">
                  <span className="absolute left-0 top-0 size-10 border-l border-t border-[var(--edge-live)]" />
                  <span className="absolute right-0 top-0 size-10 border-r border-t border-[var(--edge-live)]" />
                  <span className="absolute left-0 bottom-0 size-10 border-l border-b border-[var(--edge-live)]" />
                  <span className="absolute right-0 bottom-0 size-10 border-r border-b border-[var(--edge-live)]" />
                </div>

                {/* CANLI + FPS + pan — top-left */}
                <div className="absolute top-5 left-5 flex items-center gap-2">
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--accent-status-edge)] bg-[color-mix(in_oklch,var(--p-graphite-990)_78%,transparent)] px-2.5 py-1 font-mono text-[var(--p-text-3xs)] tracking-widest" style={{ color: "var(--accent-status-soft)" }}>
                    <span className="size-1.5 animate-pulse rounded-full bg-[var(--accent-status)]" />
                    CANLI
                  </span>
                  <span className="rounded bg-[color-mix(in_oklch,var(--p-graphite-990)_70%,transparent)] px-2 py-0.5 font-mono text-[var(--p-text-3xs)] text-[var(--measure)]">
                    {fps} fps
                  </span>
                  {/* Pan position indicator */}
                  {activeZoom > 1 && hasPan && (
                    <span className="flex items-center gap-1 rounded bg-[color-mix(in_oklch,var(--p-graphite-990)_70%,transparent)] px-2 py-0.5 font-mono text-[var(--p-text-3xs)] text-[var(--measure)]">
                      <Move className="size-2.5" />
                      X{panOffset.x > 0 ? "+" : ""}{Math.round(panOffset.x)}{" "}
                      Y{panOffset.y > 0 ? "+" : ""}{Math.round(panOffset.y)}
                    </span>
                  )}
                </div>

                {/* Active condition label */}
                <div className="absolute bottom-20 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-black/70 border border-[rgba(0,212,255,0.2)] font-mono text-[11px] text-slate-200 whitespace-nowrap">
                  {t(activeMeta.name)}
                  <span className="ml-2 text-slate-500">— {t(activeMeta.label)}</span>
                </div>

                {/* Bottom control bar */}
                <div className="absolute bottom-0 inset-x-0 flex items-center justify-center gap-3 px-5 py-4 bg-gradient-to-t from-black/85 via-black/40 to-transparent">
                  <button
                    onClick={stopCamera}
                    className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-red-500/15 border border-red-500/40 text-red-400 text-xs font-bold tracking-wide transition-all duration-300 hover:bg-red-500/25 hover:shadow-[0_0_16px_rgba(239,68,68,0.25)]"
                  >
                    <CameraOff className="size-4" />
                    {t("Durdur")}
                  </button>
                  <button
                    onClick={handleScreenshot}
                    className="btn btn-ghost"
                  >
                    <Download className="size-4" />
                    {t("Ekran Görüntüsü")}
                  </button>
                </div>
              </>
            )}

            {/* Zoom badge — top-right */}
            <div className="absolute right-5 top-5 flex items-center gap-1 rounded border border-[var(--edge-live)] bg-[color-mix(in_oklch,var(--p-graphite-990)_78%,transparent)] px-2.5 py-1 font-mono text-[var(--p-text-3xs)] text-[var(--measure)]">
              <ZoomIn className="size-3" />
              {activeZoom}×
            </div>

            {/* Minimap */}
            <Minimap zoom={activeZoom} panX={panOffset.x} panY={panOffset.y} />

            {/* Pan hint tooltip */}
            {showPanHint && (
              <div className="absolute bottom-24 left-1/2 -translate-x-1/2 px-3 py-1.5 rounded-lg bg-[#00D4FF]/15 border border-[#00D4FF]/40 font-mono text-[11px] text-[#00D4FF] whitespace-nowrap animate-fade-in">
                {t("Görüntüyü keşfetmek için sürükleyin")}
              </div>
            )}
          </div>
        </div>

        {/* ================================================================ */}
        {/* RIGHT — controls (30%)                                           */}
        {/* ================================================================ */}
        <div className="flex-[3] flex flex-col gap-4 overflow-y-auto min-w-0">

          {/* ── Zoom ─────────────────────────────────────────────────────── */}
          <div className="vis-plate shrink-0">
            <p className="vis-plate-head t-dial">
              <ZoomIn className="size-3.5" /> {t("Yaklaştırma")}
            </p>
            <div className="vis-zoom" role="group" aria-label={t("Yaklaştırma")}>
              {ZOOM_LEVELS.map((z) => (
                <button
                  key={z}
                  onClick={() => handleZoom(z)}
                  aria-pressed={activeZoom === z}
                  className="vis-zoom-btn"
                >
                  {z}×
                </button>
              ))}
            </div>
            {activeZoom > 1 && (
              <p className="t-dial mt-[var(--p-space-3)] flex items-center gap-1">
                <Move className="size-2.5" />
                {t("Görüntüyü taşımak için sürükleyin")}
              </p>
            )}
          </div>

          {/* ── Şiddet kadranı + karşılaştırma ────────────────────────────── */}
          <div className="vis-plate shrink-0">
            <p className="vis-plate-head t-dial">
              <SlidersHorizontal className="size-3.5" /> {t("Şiddet")}
            </p>

            <div className="flex items-baseline justify-between gap-2">
              <span className="t-dial">{t(activeMeta.name)}</span>
              <span className="t-measure">{pct(Math.round(severity * 100), locale)}</span>
            </div>

            <input
              type="range"
              min={0}
              max={100}
              value={Math.round(severity * 100)}
              onChange={(e) => changeSeverity(Number(e.target.value) / 100)}
              disabled={activeCondition === "normal"}
              className="vis-range mt-[var(--p-space-2)]"
              aria-label={t("Durum şiddeti")}
            />
            <p className="mt-[var(--p-space-1)] flex justify-between">
              <span className="t-dial">{t("Hafif")}</span>
              <span className="t-dial">{t("Orta")}</span>
              <span className="t-dial">{t("İleri")}</span>
            </p>

            <button
              onClick={() => setSplit((v) => (v === null ? 0.5 : null))}
              aria-pressed={split !== null}
              disabled={!isStreaming || activeCondition === "normal"}
              className="btn btn-ghost mt-[var(--p-space-3)] w-full disabled:opacity-40"
            >
              <Columns2 className="size-3.5" />
              {t(
                split !== null
                  ? "Karşılaştırmayı kapat"
                  : "Sağlıklı göz ile karşılaştır"
              )}
            </button>
          </div>

          {/* ── Eye conditions (grouped) ──────────────────────────────────── */}
          <div className="vis-plate">
            <div className="mb-[var(--p-space-3)]">
              <p className="vis-plate-head t-dial mb-[var(--p-space-1)]">
                <Eye className="size-3.5" /> {t("Göz Durumu")}
              </p>
              <p className="text-[var(--p-text-3xs)] text-[var(--ink-faint)]">
                {t("Bir göz hastalığı seçin")}
              </p>
            </div>

            <ConditionPicker
              items={pickerItems}
              activeId={activeCondition}
              onSelect={(id) => handleCondition(id as EyeCondition)}
            />
          </div>

          {/* ── Info panel ──────────────────────────────────────────────── */}
          <div className="vis-info shrink-0">
            <p className="t-dial flex items-center gap-1.5">
              <Info className="size-3.5" style={{ color: "var(--accent-status)" }} />
              {t("Bilgi")}
            </p>
            <div className="grid gap-[var(--p-space-2)]">
              <p
                className="font-display text-[var(--p-text-md)] leading-tight text-[var(--ink-title)]"
                style={{ fontWeight: "var(--p-weight-black)" }}
              >
                {t(activeMeta.name)}
              </p>
              <p className="text-[var(--p-text-xs)] leading-relaxed text-[var(--ink-body)]">
                {t(activeMeta.description)}
              </p>
              <p className="grid gap-[var(--p-space-1)] border-t border-[var(--edge-hair)] pt-[var(--p-space-2)]">
                <span className="t-dial">{t("Görülme oranı")}</span>
                <span className="t-measure">{t(activeMeta.prevalence)}</span>
              </p>
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
              className="btn btn-ghost w-full"
            >
              <MessageSquare className="size-3.5" />
              {t("Bu hastalık hakkında AI'a sor")}
            </button>
          </div>
        </div>
        </div>
      </div>
    </>
  );
}
