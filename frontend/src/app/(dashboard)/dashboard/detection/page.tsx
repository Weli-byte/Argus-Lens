"use client";

import React, {
  useRef,
  useState,
  useEffect,
  useCallback,
  useMemo,
} from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Scan,
  Search,
  Upload,
  X,
  Download,
  Eye,
  EyeOff,
  Filter,
  Move,
} from "lucide-react";
import { cn } from "@/lib/utils";
import ParticleField from "@/components/ui/ParticleField";
import { config } from "@/lib/config";
import { getAccessToken } from "@/lib/api-client";
import { translateLabel } from "@/lib/object-translations";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const COLORS = [
  "#00D4FF", "#7C3AED", "#10B981", "#F59E0B",
  "#EF4444", "#EC4899", "#8B5CF6", "#06B6D4",
  "#84CC16", "#F97316", "#6366F1", "#14B8A6",
  "#F43F5E", "#A855F7", "#22D3EE", "#4ADE80",
] as const;

const ZOOM_LEVELS = [1, 2, 4, 8] as const;
type ZoomLevel = (typeof ZOOM_LEVELS)[number];

const PRESETS = [
  { label: "İnsan & Yüz", query: "person, face, hand" },
  { label: "Araç",        query: "car, truck, bus, motorcycle, bicycle" },
  { label: "Hayvan",      query: "dog, cat, bird, horse, cow, elephant" },
  { label: "Mobilya",     query: "chair, couch, bed, dining table, desk" },
  { label: "Yiyecek",     query: "banana, apple, sandwich, pizza, cake, food" },
] as const;

const TURKISH_QUERY: Record<string, string> = {
  araba: "car", arabalar: "car", otomobil: "car",
  insan: "person", insanlar: "person",
  kişi: "person", adam: "man", kadın: "woman",
  çocuk: "child", bebek: "baby",
  köpek: "dog", kedi: "cat", kuş: "bird",
  at: "horse", inek: "cow", fil: "elephant", koyun: "sheep",
  ayı: "bear", zebra: "zebra", zürafa: "giraffe",
  aslan: "lion", kaplan: "tiger",
  ağaç: "tree", palmiye: "palm tree", çiçek: "flower", bitki: "plant",
  yüz: "face", el: "hand", göz: "eye",
  telefon: "phone", bilgisayar: "laptop",
  sandalye: "chair", masa: "table",
  yatak: "bed", kanepe: "couch",
  kitap: "book", bardak: "cup", şişe: "bottle", tabak: "plate",
  muz: "banana", elma: "apple", pizza: "pizza",
  ekmek: "bread", meyve: "fruit", sebze: "vegetable",
  köprü: "bridge", bina: "building",
  yol: "road", bisiklet: "bicycle",
  kamyon: "truck", otobüs: "bus", uçak: "airplane",
  tren: "train", tekne: "boat", motosiklet: "motorcycle",
  tabela: "sign", sokak: "street",
  hayvan: "animal", araç: "vehicle",
  yiyecek: "food", mobilya: "furniture",
  ev: "house", park: "park", okul: "school",
  hastane: "hospital", market: "store",
  dağ: "mountain", deniz: "sea", göl: "lake",
  bulut: "cloud", güneş: "sun", trafik: "traffic",
  çanta: "bag", ayakkabı: "shoe", gözlük: "glasses",
  şapka: "hat", saat: "clock",
  // Colors
  siyah: "black", beyaz: "white", kırmızı: "red", kirmizi: "red",
  mavi: "blue", yeşil: "green", yesil: "green", sarı: "yellow", sari: "yellow",
  gri: "gray", turuncu: "orange", pembe: "pink", mor: "purple", kahverengi: "brown",
  // Adjectives
  büyük: "large", buyuk: "large", küçük: "small", kucuk: "small",
  genç: "young", genc: "young", yaşlı: "old", yasli: "old",
  yeni: "new", eski: "old", uzun: "tall", kısa: "short", kisa: "short",
  // Road / Traffic
  "trafik levhası": "traffic sign", "trafik levhasi": "traffic sign",
  "trafik işareti": "traffic sign", "trafik isareti": "traffic sign",
  "yaya geçidi": "crosswalk", "yaya gecidi": "crosswalk",
  "trafik ışığı": "traffic light", "trafik isigi": "traffic light",
  "trafik ışıkları": "traffic light", "trafik isiklari": "traffic light",
  levha: "sign", işaret: "sign", isaret: "sign",
  kaldırım: "sidewalk", kaldirim: "sidewalk",
};

const TURKISH_CHARS = /[ğüşıöçĞÜŞİÖÇ]/;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Detection {
  id: number;
  box: [number, number, number, number]; // x1, y1, x2, y2 in original image px
  label: string;                          // English label from model
  labelTr: string;                        // Turkish label
  score: number;
  color: string;
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function detectLang(input: string): "tr" | "en" {
  if (!input.trim()) return "en";
  if (TURKISH_CHARS.test(input)) return "tr";
  if (input.toLowerCase().split(/[\s,]+/).some((w) => w in TURKISH_QUERY)) return "tr";
  return "en";
}

// Translates Turkish→English without synonym expansion.
// "araba" → "car" (not "car, vehicle, automobile" which causes duplicate detections).
function translateOnly(input: string): string {
  const terms = input.split(",").map((t) => t.trim().toLowerCase()).filter(Boolean);
  const translated = terms.map((t) => {
    if (TURKISH_QUERY[t]) return TURKISH_QUERY[t];
    // Word-by-word fallback
    const words = t.split(/\s+/);
    const trWords = words.map((w) => TURKISH_QUERY[w] ?? w);
    return trWords.join(" ");
  });
  return [...new Set(translated)].join(", ");
}

function drawDetections(
  canvas: HTMLCanvasElement,
  imageEl: HTMLImageElement,
  detections: Detection[],
  selectedLabel: string | null,
  debug = false
): void {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  // offsetWidth/Height reflect the CSS-constrained layout size (pre-CSS-transform).
  // The pan/zoom CSS transform is on the parent wrapper, so these are unaffected.
  const displayW = imageEl.offsetWidth;
  const displayH = imageEl.offsetHeight;
  if (displayW === 0 || displayH === 0) return;

  const naturalW = imageEl.naturalWidth  || displayW;
  const naturalH = imageEl.naturalHeight || displayH;

  // Match logical canvas size to display size for 1:1 pixel mapping.
  canvas.width  = displayW;
  canvas.height = displayH;

  const scaleX = displayW / naturalW;
  const scaleY = displayH / naturalH;

  ctx.clearRect(0, 0, displayW, displayH);

  const fontSize = Math.max(11, Math.round(displayW / 80));
  ctx.font = `bold ${fontSize}px "JetBrains Mono", monospace`;

  detections.forEach(({ box, label, labelTr, score, color }) => {
    const isHighlighted = selectedLabel === null || label === selectedLabel;
    const alpha = isHighlighted ? 1 : 0.12;
    const lineW = isHighlighted ? Math.max(2, displayW * 0.002) : 1;

    const [x1, y1, x2, y2] = box;
    const cx  = x1 * scaleX;
    const cy  = y1 * scaleY;
    const cbw = Math.min((x2 - x1) * scaleX, displayW - cx);
    const cbh = Math.min((y2 - y1) * scaleY, displayH - cy);

    ctx.globalAlpha = alpha;
    ctx.strokeStyle = color;
    ctx.lineWidth   = lineW;
    ctx.strokeRect(cx, cy, cbw, cbh);

    const text = `${labelTr || translateLabel(label)} ${Math.round(score * 100)}%`;
    const tw   = ctx.measureText(text).width + 8;
    const th   = fontSize + 6;
    const tagY = cy > th + 2 ? cy - th - 2 : cy + 2;

    ctx.fillStyle   = color;
    ctx.fillRect(cx, tagY, tw, th);
    ctx.fillStyle   = "#000000";
    ctx.globalAlpha = alpha;
    ctx.fillText(text, cx + 4, tagY + th - 3);
    ctx.globalAlpha = 1;
  });

  if (debug) {
    ctx.save();
    ctx.globalAlpha = 1;
    ctx.fillStyle = "rgba(0,0,0,0.72)";
    ctx.fillRect(4, 4, 230, 72);
    ctx.fillStyle = "#00D4FF";
    ctx.font = "10px monospace";
    ctx.fillText(`Image:  ${naturalW} × ${naturalH}`, 10, 20);
    ctx.fillText(`Canvas: ${displayW} × ${displayH}`, 10, 34);
    ctx.fillText(`Scale:  ${scaleX.toFixed(3)} × ${scaleY.toFixed(3)}`, 10, 48);
    ctx.fillText(`Boxes:  ${detections.length}`, 10, 62);
    ctx.restore();
  }
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ColorDot({ color }: { color: string }) {
  return (
    <span className="size-2.5 rounded-full shrink-0" style={{ backgroundColor: color }} />
  );
}

function ConfidenceBar({ score, color }: { score: number; color: string }) {
  return (
    <div className="w-full bg-[#1E293B] rounded-full h-1">
      <div
        className="h-1 rounded-full transition-all duration-300"
        style={{ width: `${Math.round(score * 100)}%`, backgroundColor: color }}
      />
    </div>
  );
}

function Minimap({
  zoom, panX, panY, maxPanX, maxPanY,
}: {
  zoom: number; panX: number; panY: number; maxPanX: number; maxPanY: number;
}) {
  if (zoom <= 1) return null;
  const vpW = 80 / zoom;
  const vpH = 60 / zoom;
  const normX = maxPanX > 0 ? panX / maxPanX : 0;
  const normY = maxPanY > 0 ? panY / maxPanY : 0;
  const rx = (40 - vpW / 2) - normX * (40 - vpW / 2);
  const ry = (30 - vpH / 2) - normY * (30 - vpH / 2);
  const clampedRx = Math.max(0, Math.min(80 - vpW, rx));
  const clampedRy = Math.max(0, Math.min(60 - vpH, ry));

  return (
    <div
      className="absolute bottom-10 right-3 rounded border border-slate-600/60 bg-black/70 overflow-hidden"
      style={{ width: 80, height: 60 }}
      title="Görüntü konumu"
    >
      <div className="absolute inset-0 border border-slate-700/40" />
      <div
        className="absolute border border-[#00D4FF] bg-[#00D4FF]/10 rounded-sm"
        style={{ left: clampedRx, top: clampedRy, width: vpW, height: vpH }}
      />
      <span className="absolute bottom-0.5 left-1 text-[7px] font-mono text-slate-500 uppercase">
        nav
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function DetectionPage() {
  // ── Search ────────────────────────────────────────────────────────────────
  const [searchInput,  setSearchInput]  = useState("");
  const [activePrompt, setActivePrompt] = useState("");

  // ── Image ─────────────────────────────────────────────────────────────────
  const [imageSrc,  setImageSrc]  = useState<string | null>(null);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imageDims, setImageDims] = useState({ w: 0, h: 0 });
  const imageRef          = useRef<HTMLImageElement>(null);
  const canvasRef         = useRef<HTMLCanvasElement>(null);
  const imageContainerRef = useRef<HTMLDivElement>(null);

  // ── Detection results ─────────────────────────────────────────────────────
  const [detections,  setDetections]  = useState<Detection[]>([]);
  const [isDetecting, setIsDetecting] = useState(false);
  const [latencyMs,   setLatencyMs]   = useState<number | null>(null);
  const [detectError, setDetectError] = useState<string | null>(null);
  const [modelUsed,   setModelUsed]   = useState<string | null>(null);
  const [promptUsed,  setPromptUsed]  = useState<string | null>(null);

  // ── Pan ───────────────────────────────────────────────────────────────────
  const [panOffset,     setPanOffset]     = useState({ x: 0, y: 0 });
  const [lastPanOffset, setLastPanOffset] = useState({ x: 0, y: 0 });
  const [isDragging,    setIsDragging]    = useState(false);
  const [dragStart,     setDragStart]     = useState({ x: 0, y: 0 });
  const [showPanHint,   setShowPanHint]   = useState(false);
  const hintShownRef = useRef(false);

  // ── UI ────────────────────────────────────────────────────────────────────
  const [zoom,          setZoom]          = useState<ZoomLevel>(1);
  const [selectedLabel, setSelectedLabel] = useState<string | null>(null);
  const [filterText,    setFilterText]    = useState("");
  const [isDragOver,    setIsDragOver]    = useState(false);
  const [showBoxes,     setShowBoxes]     = useState(true);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Derived ───────────────────────────────────────────────────────────────
  const detectedLang = useMemo(() => detectLang(searchInput), [searchInput]);

  // Show what will actually be sent to the model, but only when it differs from input.
  const translationHint = useMemo(() => {
    const clean = searchInput.trim().toLowerCase();
    if (!clean) return null;
    const translated = translateOnly(clean);
    return translated !== clean ? translated : null;
  }, [searchInput]);

  const sortedDetections = useMemo(
    () => [...detections].sort((a, b) => b.score - a.score),
    [detections]
  );

  const filteredDetections = useMemo(() => {
    if (!filterText) return sortedDetections;
    const q = filterText.toLowerCase();
    return sortedDetections.filter(
      (d) => d.label.toLowerCase().includes(q) || d.labelTr.toLowerCase().includes(q)
    );
  }, [sortedDetections, filterText]);

  // Minimap pan bounds (not hooks — reads ref during render)
  const _container = imageContainerRef.current;
  const maxPanX = (_container?.clientWidth  ?? 0) * Math.max(0, zoom - 1) / 2;
  const maxPanY = (_container?.clientHeight ?? 0) * Math.max(0, zoom - 1) / 2;

  // ── Redraw on detection / selection / visibility change ───────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    const img    = imageRef.current;
    if (!canvas || !img || imageDims.w === 0) return;
    if (!showBoxes || detections.length === 0) {
      canvas.getContext("2d")?.clearRect(0, 0, canvas.width, canvas.height);
      return;
    }
    drawDetections(canvas, img, detections, selectedLabel);
  }, [detections, selectedLabel, imageDims, showBoxes]);

  // ── ResizeObserver — redraws when image layout size changes ───────────────
  useEffect(() => {
    const img = imageRef.current;
    if (!img) return;
    const ro = new ResizeObserver(() => {
      const canvas = canvasRef.current;
      if (!canvas || detections.length === 0 || !showBoxes) return;
      drawDetections(canvas, img, detections, selectedLabel);
    });
    ro.observe(img);
    return () => ro.disconnect();
  }, [detections, selectedLabel, showBoxes]);

  // ── Reset pan on zoom change ──────────────────────────────────────────────
  useEffect(() => {
    const zero = { x: 0, y: 0 };
    setPanOffset(zero);
    setLastPanOffset(zero);
  }, [zoom]);

  // ── Image load ────────────────────────────────────────────────────────────
  const handleImageLoad = useCallback(() => {
    const img    = imageRef.current;
    const canvas = canvasRef.current;
    if (!img) return;
    setImageDims({ w: img.naturalWidth, h: img.naturalHeight });
    // Pre-size canvas so it's ready before first detection
    if (canvas) {
      canvas.width  = img.offsetWidth  || img.naturalWidth;
      canvas.height = img.offsetHeight || img.naturalHeight;
    }
  }, []);

  // ── File handling ─────────────────────────────────────────────────────────
  const loadFile = useCallback((file: File) => {
    if (!file.type.match(/^image\/(jpeg|png|webp)$/)) return;
    if (file.size > 10 * 1024 * 1024) return;
    const url = URL.createObjectURL(file);
    setImageSrc(url);
    setImageFile(file);
    setDetections([]);
    setSelectedLabel(null);
    setLatencyMs(null);
    setDetectError(null);
    setPromptUsed(null);
    setShowBoxes(true);
  }, []);

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const f = e.target.files?.[0];
      if (f) loadFile(f);
      e.target.value = "";
    },
    [loadFile]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragOver(false);
      const f = e.dataTransfer.files[0];
      if (f) loadFile(f);
    },
    [loadFile]
  );

  // ── Detect ────────────────────────────────────────────────────────────────
  const handleDetect = useCallback(async () => {
    // Automatically sync searchInput if user clicks "Tespit Et" directly
    const currentPrompt = searchInput.trim() ? searchInput : activePrompt;
    if (!imageFile || !currentPrompt.trim()) return;

    const effectivePrompt = translateOnly(currentPrompt);
    setActivePrompt(currentPrompt);

    setIsDetecting(true);
    setDetectError(null);
    setDetections([]);
    setSelectedLabel(null);
    setPromptUsed(effectivePrompt);

    try {
      const dataUrl = await fileToDataUrl(imageFile);
      const token   = getAccessToken();

      const res = await fetch(`${config.api.baseUrl}/api/v1/detect`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          image_base64:         dataUrl,
          prompt:               currentPrompt,
          confidence_threshold: 0.25,
          language:             detectedLang,
        }),
      });

      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        const detail  = errBody.detail;
        throw new Error(
          Array.isArray(detail)
            ? detail.map((d: { msg?: string }) => d.msg ?? "").join("; ")
            : String(detail ?? `HTTP ${res.status}`)
        );
      }

      const data = await res.json();
      let dets: Detection[] = [];

      if (data.boxes && data.boxes.length > 0) {
        const firstBox = data.boxes[0];

        if (Array.isArray(firstBox)) {
          // Legacy flat-array format: [[x1,y1,x2,y2], ...]
          const colorMap = new Map<string, string>();
          dets = (data.boxes as number[][]).map((box, i) => {
            const label = (data.labels as string[])[i] ?? "object";
            if (!colorMap.has(label))
              colorMap.set(label, COLORS[colorMap.size % COLORS.length]);
            return {
              id: i, box: box as [number, number, number, number],
              label, labelTr: translateLabel(label),
              score: (data.scores as number[])[i] ?? 0,
              color: colorMap.get(label)!,
            };
          });
        } else {
          // BoundingBox object format: [{x1, y1, x2, y2, label, label_tr, score, color}]
          dets = (data.boxes as {
            x1: number; y1: number; x2: number; y2: number;
            label: string; label_tr: string; score: number; color: string;
          }[]).map((b, i) => ({
            id: i, box: [b.x1, b.y1, b.x2, b.y2] as [number, number, number, number],
            label: b.label, labelTr: b.label_tr ?? translateLabel(b.label),
            score: b.score, color: b.color,
          }));
        }
      }

      setDetections(dets);
      setLatencyMs(data.latency_ms ?? null);
      setModelUsed(data.model_used ?? data.model ?? null);
      if (data.prompt_used) setPromptUsed(data.prompt_used);
    } catch (err) {
      setDetectError(err instanceof Error ? err.message : "Tespit başarısız");
    } finally {
      setIsDetecting(false);
    }
  }, [imageFile, activePrompt, detectedLang]);

  // ── Search / preset ───────────────────────────────────────────────────────
  const handleSearch = useCallback(() => {
    if (searchInput.trim()) setActivePrompt(searchInput);
  }, [searchInput]);

  const handlePreset = useCallback((query: string) => {
    setSearchInput(query);
    setActivePrompt(query);
  }, []);

  const handleSearchKey = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") handleSearch();
    },
    [handleSearch]
  );

  // ── Zoom ──────────────────────────────────────────────────────────────────
  const handleZoom = useCallback((z: ZoomLevel) => {
    setZoom(z);
    if (z > 1 && !hintShownRef.current) {
      hintShownRef.current = true;
      setShowPanHint(true);
      setTimeout(() => setShowPanHint(false), 2200);
    }
  }, []);

  // ── Pan — mouse (handlers on outer div, canvas has pointerEvents: none) ───
  const handleMouseDown = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (zoom <= 1) return;
      e.preventDefault();
      setIsDragging(true);
      setDragStart({ x: e.clientX - lastPanOffset.x, y: e.clientY - lastPanOffset.y });
    },
    [zoom, lastPanOffset]
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (!isDragging) return;
      const c  = imageContainerRef.current;
      const mX = c ? c.clientWidth  * (zoom - 1) / 2 : 0;
      const mY = c ? c.clientHeight * (zoom - 1) / 2 : 0;
      const nx = Math.max(-mX, Math.min(mX, e.clientX - dragStart.x));
      const ny = Math.max(-mY, Math.min(mY, e.clientY - dragStart.y));
      setPanOffset({ x: nx, y: ny });
    },
    [isDragging, dragStart, zoom]
  );

  const handleMouseUp = useCallback(() => {
    if (isDragging) {
      setIsDragging(false);
      setLastPanOffset(panOffset);
    }
  }, [isDragging, panOffset]);

  const handleMouseLeave = useCallback(() => {
    if (isDragging) {
      setIsDragging(false);
      setLastPanOffset(panOffset);
    }
  }, [isDragging, panOffset]);

  // ── Pan — touch ───────────────────────────────────────────────────────────
  const handleTouchStart = useCallback(
    (e: React.TouchEvent<HTMLDivElement>) => {
      if (zoom <= 1) return;
      const t = e.touches[0];
      setIsDragging(true);
      setDragStart({ x: t.clientX - lastPanOffset.x, y: t.clientY - lastPanOffset.y });
    },
    [zoom, lastPanOffset]
  );

  const handleTouchMove = useCallback(
    (e: React.TouchEvent<HTMLDivElement>) => {
      if (!isDragging) return;
      e.preventDefault();
      const t  = e.touches[0];
      const c  = imageContainerRef.current;
      const mX = c ? c.clientWidth  * (zoom - 1) / 2 : 0;
      const mY = c ? c.clientHeight * (zoom - 1) / 2 : 0;
      const nx = Math.max(-mX, Math.min(mX, t.clientX - dragStart.x));
      const ny = Math.max(-mY, Math.min(mY, t.clientY - dragStart.y));
      setPanOffset({ x: nx, y: ny });
    },
    [isDragging, dragStart, zoom]
  );

  const handleTouchEnd = useCallback(() => {
    setIsDragging(false);
    setLastPanOffset(panOffset);
  }, [panOffset]);

  // ── Label click ───────────────────────────────────────────────────────────
  const handleLabelClick = useCallback((label: string) => {
    setSelectedLabel((prev) => (prev === label ? null : label));
  }, []);

  // ── Controls ──────────────────────────────────────────────────────────────
  const handleShowAll = useCallback(() => {
    setSelectedLabel(null);
    setShowBoxes(true);
  }, []);

  const handleClear = useCallback(() => {
    setDetections([]);
    setSelectedLabel(null);
    setLatencyMs(null);
    setDetectError(null);
    setPromptUsed(null);
    const canvas = canvasRef.current;
    if (canvas) canvas.getContext("2d")?.clearRect(0, 0, canvas.width, canvas.height);
  }, []);

  const handleExport = useCallback(() => {
    const imgEl = imageRef.current;
    if (!imgEl || imageDims.w === 0) return;

    const out = document.createElement("canvas");
    out.width  = imageDims.w;
    out.height = imageDims.h;
    const ctx  = out.getContext("2d")!;
    ctx.drawImage(imgEl, 0, 0, imageDims.w, imageDims.h);

    if (detections.length > 0) {
      const tmpCanvas = document.createElement("canvas");
      tmpCanvas.width  = imageDims.w;
      tmpCanvas.height = imageDims.h;
      // Override layout size so drawDetections computes 1:1 scale
      Object.assign(imgEl.style, { width: `${imageDims.w}px`, height: `${imageDims.h}px` });
      drawDetections(tmpCanvas, imgEl, detections, selectedLabel);
      Object.assign(imgEl.style, { width: "", height: "" });
      ctx.drawImage(tmpCanvas, 0, 0);
    }

    const link    = document.createElement("a");
    link.href     = out.toDataURL("image/png");
    link.download = "argus-detection.png";
    link.click();
  }, [imageDims, detections, selectedLabel]);

  // ── Cleanup ───────────────────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      if (imageSrc) URL.revokeObjectURL(imageSrc);
    };
  }, [imageSrc]);

  // ── Derived flags ─────────────────────────────────────────────────────────
  const hasImage   = imageSrc !== null;
  const hasResults = detections.length > 0;
  const canDetect  = hasImage && activePrompt.trim().length > 0;
  const hasPan     = panOffset.x !== 0 || panOffset.y !== 0;

  const cursorStyle: React.CSSProperties =
    zoom > 1
      ? { cursor: isDragging ? "grabbing" : "grab" }
      : { cursor: "default" };

  // ─────────────────────────────────────────────────────────────────────────

  return (
    <div
      className="flex flex-col gap-3 overflow-hidden"
      style={{ height: "calc(100vh - 57px - 48px)" }}
    >
      {/* hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="hidden"
        onChange={handleFileInput}
      />

      {/* ================================================================== */}
      {/* Page header                                                        */}
      {/* ================================================================== */}
      <div className="shrink-0">
        <p className="text-[11px] text-slate-500 tracking-[0.25em] uppercase mb-1">
          ArgusLens <span className="text-slate-700">/</span>{" "}
          <span className="text-cyan-400">Nesne Tespiti</span>
        </p>
        <h1 className="text-3xl leading-none font-black tracking-tighter uppercase">
          <span className="text-white">NESNE</span>{" "}
          <span className="text-cyan-400 drop-shadow-[0_0_24px_rgba(0,212,255,0.4)]">TESPİTİ</span>
        </h1>
        <div className="w-16 h-0.5 bg-gradient-to-r from-cyan-400 to-transparent rounded-full mt-2" />
      </div>

      {/* ================================================================== */}
      {/* TOP — Search bar                                                   */}
      {/* ================================================================== */}
      <div className="shrink-0 space-y-2">
        {/* Main row — premium search bar */}
        <div className="relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 size-5 text-cyan-400 pointer-events-none" />
          <input
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={handleSearchKey}
            placeholder="Nesne adı yazın... (örn: araba, insan, bina)"
            className="w-full h-14 pl-12 pr-44 rounded-[14px] bg-[#0D1117] border-2 border-[rgba(0,212,255,0.2)] text-base text-slate-200 placeholder-slate-600 focus:outline-none focus:border-cyan-400 focus:shadow-[0_0_20px_rgba(0,212,255,0.15)] transition-all duration-300"
          />
          <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-2">
            {searchInput.trim() && (
              <span
                className={cn(
                  "text-[10px] font-mono font-bold px-2 py-1 rounded-md pointer-events-none",
                  detectedLang === "tr"
                    ? "bg-amber-400/10 text-amber-400 border border-amber-400/20"
                    : "bg-blue-400/10 text-blue-400 border border-blue-400/20"
                )}
              >
                {detectedLang === "tr" ? "TR" : "EN"}
              </span>
            )}
            <button
              onClick={handleSearch}
              disabled={!searchInput.trim()}
              className={cn(
                "px-6 h-10 rounded-[10px] text-sm font-bold tracking-wide transition-all duration-300 shrink-0",
                searchInput.trim()
                  ? "bg-gradient-to-r from-cyan-500 to-sky-500 text-[#080B0F] hover:shadow-[0_0_16px_rgba(0,212,255,0.4)] hover:brightness-110"
                  : "bg-[#111827] text-slate-600 cursor-not-allowed"
              )}
            >
              TARA
            </button>
          </div>
        </div>

        {/* Hint row */}
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <p className="text-[11px] font-mono text-slate-600">
            💡 İpucu: Birden fazla nesne için virgülle ayırın: &apos;araba, insan, ağaç&apos;
          </p>
          {translationHint && (
            <p className="text-[11px] font-mono text-slate-500">
              🔍 Gönderilen:{" "}
              <span className="text-cyan-600">{translationHint}</span>
            </p>
          )}
        </div>

        {/* Preset chips */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-slate-500 uppercase tracking-wider shrink-0">
            Hazır:
          </span>
          {PRESETS.map((p) => (
            <button
              key={p.label}
              onClick={() => handlePreset(p.query)}
              className={cn(
                "px-3 py-1 rounded-[20px] text-sm border transition-all duration-300",
                activePrompt === p.query
                  ? "border-cyan-500 bg-cyan-500/10 text-cyan-400"
                  : "border-slate-700 text-slate-400 hover:border-cyan-500 hover:text-cyan-400"
              )}
            >
              {p.label}
            </button>
          ))}
          {promptUsed && (
            <span className="ml-auto text-[10px] font-mono text-slate-600 truncate max-w-xs" title={promptUsed}>
              → {promptUsed}
            </span>
          )}
        </div>
      </div>

      {/* ================================================================== */}
      {/* MIDDLE — image + results                                           */}
      {/* ================================================================== */}
      <div className="flex gap-4 flex-1 min-h-0">

        {/* ──────────────────────────────────────────────────────────────── */}
        {/* LEFT 70%                                                        */}
        {/* ──────────────────────────────────────────────────────────────── */}
        <div className="flex-[7] flex flex-col gap-2 min-w-0">

          {/* Status row */}
          <div className="flex items-center justify-between shrink-0 min-h-[20px]">
            <div className="flex items-center gap-2">
              {(isDetecting || hasResults || modelUsed) && (
                <Scan className="size-4 text-cyan-400" />
              )}
              {isDetecting && (
                <span className="flex items-center gap-1 text-[10px] font-mono text-amber-400">
                  <span className="size-1.5 rounded-full bg-amber-400 animate-pulse" />
                  TARANYOR
                </span>
              )}
              {hasResults && !isDetecting && (
                <span className="flex items-center gap-1 text-[10px] font-mono text-cyan-400">
                  <span className="size-1.5 rounded-full bg-cyan-400" />
                  {detections.length} NESNE
                </span>
              )}
              {modelUsed && !isDetecting && (
                <span className="text-[10px] font-mono text-slate-600 px-1.5 py-0.5 rounded bg-slate-800/50">
                  {modelUsed}
                </span>
              )}
            </div>

          </div>

          {/* Image area */}
          <div
            ref={imageContainerRef}
            className={cn(
              "relative flex-1 rounded-[20px] border-2 bg-[#080B0F] overflow-hidden min-h-0 flex items-center justify-center transition-all duration-300",
              hasImage
                ? "border-[rgba(0,212,255,0.2)]"
                : isDragOver
                  ? "border-solid border-cyan-400 bg-[rgba(0,212,255,0.05)] scale-[1.01]"
                  : "border-dashed border-[rgba(0,212,255,0.2)]"
            )}
          >
            {/* Zoom — round buttons, top-right */}
            {hasImage && (
              <div className="absolute top-3 right-3 flex items-center gap-1.5 z-20">
                {ZOOM_LEVELS.map((z) => (
                  <button
                    key={z}
                    onClick={() => handleZoom(z)}
                    className={cn(
                      "size-8 rounded-full text-[11px] font-mono font-semibold border transition-all duration-300",
                      zoom === z
                        ? "bg-cyan-500 text-black border-cyan-500 shadow-[0_0_10px_rgba(0,212,255,0.4)]"
                        : "bg-black/60 border-slate-700 text-slate-400 hover:border-cyan-500 hover:text-cyan-400"
                    )}
                  >
                    {z}×
                  </button>
                ))}
              </div>
            )}
            {!hasImage ? (
              /* Upload zone */
              <div
                className={cn(
                  "group relative flex flex-col items-center justify-center gap-5 w-full h-full cursor-pointer select-none transition-all duration-300 overflow-hidden",
                  isDragOver ? "bg-cyan-500/5" : "hover:bg-cyan-500/[0.02]"
                )}
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
                onDragLeave={() => setIsDragOver(false)}
                onDrop={handleDrop}
              >
                <ParticleField density={40} className="absolute inset-0 w-full h-full pointer-events-none" />
                {/* Corner brackets — glow on hover */}
                <span className="absolute left-4 top-4 size-8 border-l-2 border-t-2 border-cyan-400 rounded-tl-lg opacity-30 group-hover:opacity-100 transition-opacity duration-300" />
                <span className="absolute right-4 top-4 size-8 border-r-2 border-t-2 border-cyan-400 rounded-tr-lg opacity-30 group-hover:opacity-100 transition-opacity duration-300" />
                <span className="absolute left-4 bottom-4 size-8 border-l-2 border-b-2 border-cyan-400 rounded-bl-lg opacity-30 group-hover:opacity-100 transition-opacity duration-300" />
                <span className="absolute right-4 bottom-4 size-8 border-r-2 border-b-2 border-cyan-400 rounded-br-lg opacity-30 group-hover:opacity-100 transition-opacity duration-300" />
                <div className={cn(
                  "relative size-24 rounded-3xl border flex items-center justify-center transition-all duration-300",
                  isDragOver
                    ? "bg-cyan-500/15 border-cyan-500/50 shadow-[0_0_24px_rgba(0,212,255,0.2)]"
                    : "bg-cyan-500/5 border-[rgba(0,212,255,0.2)]"
                )}>
                  <Upload className="size-12 text-cyan-400 transition-transform duration-300 group-hover:rotate-[15deg]" strokeWidth={1.5} />
                </div>
                <div className="relative text-center space-y-1">
                  <p className="text-base font-semibold text-slate-200">Görsel Yükle veya Sürükle</p>
                  <p className="text-xs text-slate-500">JPG, PNG, WebP — maks. 10 MB</p>
                </div>
              </div>
            ) : (
              /* Image + canvas */
              <div
                className="w-full h-full overflow-hidden flex items-center justify-center"
                style={cursorStyle}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseLeave}
                onTouchStart={handleTouchStart}
                onTouchMove={handleTouchMove}
                onTouchEnd={handleTouchEnd}
                onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
                onDragLeave={() => setIsDragOver(false)}
                onDrop={handleDrop}
              >
                {/* Scaled wrapper: inline-block shrink-wraps exactly around the image */}
                <div
                  style={{
                    position: "relative",
                    display: "inline-block",
                    lineHeight: 0,
                    transform: `translate(${panOffset.x}px, ${panOffset.y}px) scale(${zoom})`,
                    transformOrigin: "center",
                    transition: isDragging ? "none" : "transform 0.15s ease-out",
                  }}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    ref={imageRef}
                    src={imageSrc!}
                    alt="Detection target"
                    draggable={false}
                    onLoad={handleImageLoad}
                    className="block select-none"
                    style={{ maxHeight: "calc(100vh - 300px)", maxWidth: "100%" }}
                  />
                  {/* Canvas overlays image exactly; pointerEvents:none so pan works on outer div */}
                  <canvas
                    ref={canvasRef}
                    style={{
                      position: "absolute",
                      top: 0,
                      left: 0,
                      width: "100%",
                      height: "100%",
                      pointerEvents: "none",
                    }}
                  />
                </div>

                {/* Scan animation */}
                <AnimatePresence>
                  {isDetecting && (
                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className="absolute inset-0 bg-black/50 flex items-center justify-center z-20 overflow-hidden pointer-events-none"
                    >
                      <motion.div
                        className="absolute left-0 right-0 h-0.5 bg-cyan-400"
                        style={{ boxShadow: "0 0 10px 4px rgba(0,212,255,0.55)" }}
                        initial={{ top: "0%" }}
                        animate={{ top: ["0%", "100%", "0%"] }}
                        transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                      />
                      <p className="font-mono text-xs text-cyan-400 animate-pulse z-10 mt-16">
                        Tespit ediliyor…
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Clear image */}
                <button
                  onClick={() => {
                    setImageSrc(null);
                    setImageFile(null);
                    setImageDims({ w: 0, h: 0 });
                    handleClear();
                  }}
                  className="absolute top-3 left-3 size-7 rounded-lg bg-black/60 border border-slate-700 flex items-center justify-center text-slate-400 hover:text-red-400 hover:border-red-500/40 transition-all z-10"
                  title="Görseli kaldır"
                >
                  <X className="size-3.5" />
                </button>

                {/* Latency / pan badges */}
                <div className="absolute top-14 right-3 flex items-center gap-1.5 z-10">
                  {latencyMs !== null && (
                    <span className="px-2 py-0.5 rounded bg-black/60 font-mono text-[10px] text-cyan-400">
                      {Math.round(latencyMs)} ms
                    </span>
                  )}
                  {zoom > 1 && hasPan && (
                    <span className="px-2 py-0.5 rounded bg-black/60 font-mono text-[10px] text-cyan-400 flex items-center gap-1">
                      <Move className="size-2.5" />
                      {panOffset.x > 0 ? "+" : ""}{Math.round(panOffset.x)}{" "}
                      {panOffset.y > 0 ? "+" : ""}{Math.round(panOffset.y)}
                    </span>
                  )}
                </div>

                {/* Minimap */}
                <Minimap
                  zoom={zoom}
                  panX={panOffset.x}
                  panY={panOffset.y}
                  maxPanX={maxPanX}
                  maxPanY={maxPanY}
                />

                {/* Pan hint */}
                {showPanHint && (
                  <div className="absolute bottom-16 left-1/2 -translate-x-1/2 px-3 py-1.5 rounded-lg bg-[#00D4FF]/15 border border-[#00D4FF]/40 font-mono text-[11px] text-[#00D4FF] whitespace-nowrap pointer-events-none z-10">
                    Görüntüyü keşfetmek için sürükleyin
                  </div>
                )}

                {/* Error */}
                {detectError && (
                  <div className="absolute bottom-4 left-1/2 -translate-x-1/2 px-3 py-1.5 rounded-lg bg-red-500/15 border border-red-500/40 font-mono text-[11px] text-red-400 z-10 max-w-sm text-center">
                    {detectError}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* ──────────────────────────────────────────────────────────────── */}
        {/* RIGHT 30%                                                       */}
        {/* ──────────────────────────────────────────────────────────────── */}
        <div className="flex-[3] flex flex-col gap-3 min-w-0">

          {/* Detect button */}
          <button
            onClick={handleDetect}
            disabled={!canDetect || isDetecting}
            className={cn(
              "w-full h-[52px] rounded-xl text-sm font-bold tracking-wide transition-all duration-300 shrink-0 flex items-center justify-center gap-2",
              canDetect && !isDetecting
                ? "bg-gradient-to-r from-cyan-500 to-sky-500 text-[#080B0F] hover:shadow-[0_0_24px_rgba(0,212,255,0.4)] hover:brightness-110"
                : "bg-[#0D1117] border border-[#1E293B] text-slate-600 cursor-not-allowed"
            )}
          >
            <Scan className="size-4" />
            {isDetecting ? "TARANIYOR…" : "TARA"}
          </button>

          {/* Results panel */}
          <div className="card-lift rounded-2xl border border-[rgba(0,212,255,0.12)] bg-gradient-to-br from-[#0D1117] to-[#111827] p-4 flex flex-col gap-3 flex-1 min-h-0 overflow-hidden">
            <div className="space-y-2 shrink-0">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest flex items-center gap-1.5">
                  <Eye className="size-3.5 text-cyan-400" />
                  Tespit Sonuçları
                </p>
                {hasResults && (
                  <span className="text-[10px] font-mono text-cyan-600">
                    {detections.length} nesne
                  </span>
                )}
              </div>
              {hasResults && (
                <div className="relative">
                  <Filter className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3 text-slate-600" />
                  <input
                    type="text"
                    value={filterText}
                    onChange={(e) => setFilterText(e.target.value)}
                    placeholder="Sonuçlarda ara…"
                    className="w-full pl-7 pr-3 py-1.5 rounded-lg bg-[#080B0F] border border-[#1E293B] text-[11px] font-mono text-slate-300 placeholder-slate-600 focus:outline-none focus:border-cyan-500/40 transition-all"
                  />
                </div>
              )}
            </div>

            <div className="flex-1 overflow-y-auto space-y-1.5 pr-0.5">
              <AnimatePresence>
                {filteredDetections.length > 0 ? (
                  filteredDetections.map((det) => {
                    const isSel    = selectedLabel === det.label;
                    const isAnySel = selectedLabel !== null;
                    return (
                      <motion.button
                        key={det.id}
                        initial={{ opacity: 0, y: 4 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0 }}
                        onClick={() => handleLabelClick(det.label)}
                        className={cn(
                          "w-full text-left px-3 py-2.5 rounded-lg border border-l-[3px] border-l-cyan-500 transition-all duration-300",
                          isSel
                            ? "bg-cyan-500/10 border-cyan-500/50 border-l-cyan-400"
                            : isAnySel
                              ? "bg-[#080B0F] border-[rgba(255,255,255,0.06)] opacity-40 hover:opacity-70"
                              : "bg-[#080B0F] border-[rgba(255,255,255,0.06)] hover:border-cyan-500/30 hover:bg-slate-800/40"
                        )}
                      >
                        <div className="flex items-center gap-2 mb-1.5">
                          <ColorDot color={det.color} />
                          <span className={cn(
                            "text-sm font-bold flex-1 truncate",
                            isSel ? "text-cyan-400" : "text-slate-100"
                          )}>
                            {det.labelTr || translateLabel(det.label)}
                          </span>
                          <span className="text-[10px] text-slate-600 shrink-0">
                            ({det.label})
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <ConfidenceBar score={det.score} color="#00D4FF" />
                          <span className="text-xs font-bold text-cyan-400 shrink-0">
                            {Math.round(det.score * 100)}%
                          </span>
                        </div>
                      </motion.button>
                    );
                  })
                ) : !hasResults ? (
                  <div className="flex flex-col items-center justify-center h-32 gap-2 text-center">
                    <Scan className="size-8 text-slate-700" />
                    <p className="text-[11px] font-mono text-slate-600 leading-relaxed">
                      {hasImage
                        ? "Bir nesne yazın ve\nTespit Et&apos;e tıklayın"
                        : "Önce bir görsel yükleyin"}
                    </p>
                  </div>
                ) : (
                  <div className="flex items-center justify-center h-16">
                    <p className="text-[11px] font-mono text-slate-600">Sonuç bulunamadı</p>
                  </div>
                )}
              </AnimatePresence>
            </div>

            {latencyMs !== null && (
              <p className="text-xs text-slate-500 shrink-0 text-right pt-1.5 border-t border-[rgba(255,255,255,0.06)]">
                Süre: {Math.round(latencyMs)}ms
              </p>
            )}
          </div>
        </div>
      </div>

      {/* ================================================================== */}
      {/* BOTTOM — controls                                                  */}
      {/* ================================================================== */}
      <div className="shrink-0 flex items-center justify-between border-t border-[rgba(255,255,255,0.06)] px-6 py-3">
        <span className="text-sm text-slate-400">
          {hasResults
            ? `${detections.length} nesne tespit edildi`
            : hasImage
              ? "Tespit bekleniyor"
              : "Görsel yüklenmedi"}
        </span>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowBoxes((v) => !v)}
            disabled={!hasResults}
            className={cn(
              "flex items-center gap-1.5 px-3.5 py-2 rounded-lg border text-xs font-semibold transition-all duration-300",
              hasResults
                ? "border-slate-700 text-slate-400 hover:border-cyan-500 hover:text-cyan-400"
                : "border-[rgba(255,255,255,0.06)] text-slate-700 cursor-not-allowed"
            )}
          >
            {showBoxes ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
            {showBoxes ? "Kutular Gizle" : "Kutular Göster"}
          </button>
          <button
            onClick={handleShowAll}
            disabled={!hasResults}
            className={cn(
              "flex items-center gap-1.5 px-3.5 py-2 rounded-lg border text-xs font-semibold transition-all duration-300",
              hasResults
                ? "border-slate-700 text-slate-400 hover:border-cyan-500 hover:text-cyan-400"
                : "border-[rgba(255,255,255,0.06)] text-slate-700 cursor-not-allowed"
            )}
          >
            Tümünü Göster
          </button>
          <button
            onClick={handleClear}
            disabled={!hasResults}
            className={cn(
              "flex items-center gap-1.5 px-3.5 py-2 rounded-lg border text-xs font-semibold transition-all duration-300",
              hasResults
                ? "border-slate-700 text-slate-400 hover:border-red-500 hover:text-red-400"
                : "border-[rgba(255,255,255,0.06)] text-slate-700 cursor-not-allowed"
            )}
          >
            <X className="size-3.5" />
            Temizle
          </button>
          <button
            onClick={handleExport}
            disabled={!hasImage || !hasResults}
            className={cn(
              "flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-bold transition-all duration-300",
              hasImage && hasResults
                ? "bg-cyan-500 text-black hover:shadow-[0_0_16px_rgba(0,212,255,0.4)] hover:brightness-110"
                : "border border-[rgba(255,255,255,0.06)] text-slate-700 cursor-not-allowed"
            )}
          >
            <Download className="size-3.5" />
            Dışa Aktar
          </button>
        </div>
      </div>
    </div>
  );
}
