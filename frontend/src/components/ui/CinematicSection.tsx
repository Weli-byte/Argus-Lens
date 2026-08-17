"use client";

import React, { useEffect, useRef } from "react";
import { Heart, Droplet, Eye, AlertTriangle, Zap, ScanSearch, Brain, ShieldCheck } from "lucide-react";

/**
 * Cinematic full-height scroll panels for the dashboard.
 * Purely decorative — IntersectionObserver adds .visible to .reveal elements.
 */

// ECG waveform path: flat line with a spike every 100px across 1600px
function buildEcgPath(): string {
  let d = "M0,50";
  for (let x = 0; x < 1600; x += 100) {
    d += ` L${x + 20},50 L${x + 30},20 L${x + 40},80 L${x + 50},50 L${x + 100},50`;
  }
  return d;
}

const ECG_PATH = buildEcgPath();

// ── Panel 2 detection overlay ───────────────────────────────────────────────
// Simple wireframe glyphs drawn in local ~0-44 coordinates, placed inside a
// <g transform="translate(...)"> per card.
const DETECTION_ICONS: Record<string, React.ReactNode> = {
  car: (
    <g stroke="#00D4FF" strokeWidth={1.2} fill="rgba(0,212,255,0.08)" strokeLinejoin="round">
      <path d="M4,24 L8,14 L16,10 L32,10 L40,14 L44,24 L44,28 L4,28 Z" />
      <path d="M17,14 L20,18 L28,18 L31,14" fill="none" />
      <circle cx="14" cy="28" r="4" fill="#080B0F" />
      <circle cx="34" cy="28" r="4" fill="#080B0F" />
    </g>
  ),
  human: (
    <g stroke="#00D4FF" strokeWidth={1.2} fill="none" strokeLinecap="round">
      <circle cx="15" cy="6" r="4" fill="rgba(0,212,255,0.1)" />
      <line x1="15" y1="10" x2="15" y2="24" />
      <line x1="6" y1="15" x2="24" y2="15" />
      <line x1="15" y1="24" x2="8" y2="36" />
      <line x1="15" y1="24" x2="22" y2="36" />
    </g>
  ),
  cup: (
    <g stroke="#00D4FF" strokeWidth={1.2} fill="rgba(0,212,255,0.08)">
      <path d="M8,8 L8,26 Q8,30 12,30 L24,30 Q28,30 28,26 L28,8 Z" />
      <path d="M28,12 Q36,12 36,18 Q36,24 28,24" fill="none" />
    </g>
  ),
};

const DETECTION_CARDS = [
  { key: "arac", label: "NESNE: ARAÇ", conf: "GÜVEN: 94%", x: 16, y: 46, w: 132, h: 112, anchor: [168, 210] as [number, number], edge: [148, 102] as [number, number], icon: "car" },
  { key: "insan", label: "NESNE: İNSAN", conf: "GÜVEN: 97%", x: 296, y: 92, w: 128, h: 112, anchor: [236, 222] as [number, number], edge: [296, 148] as [number, number], icon: "human" },
  { key: "kupa", label: "NESNE: KUPA", conf: "GÜVEN: 91%", x: 16, y: 366, w: 128, h: 118, anchor: [198, 278] as [number, number], edge: [80, 366] as [number, number], icon: "cup" },
];

// ── Panel 3 vitals ───────────────────────────────────────────────────────────
const VITAL_CARDS = [
  { icon: Heart, n: "74", l: "NABIZ (BPM)", s: "● Normal" },
  { icon: Droplet, n: "%98.2", l: "OKSİJEN (SpO2)", s: "● Optimal" },
  { icon: Eye, n: "15.1", l: "GÖZ BASINCI", s: "mmHg" },
  { icon: AlertTriangle, n: "%12", l: "AI RİSK SKORU", s: "● Düşük Risk" },
];

// 60-second live trend: smooth deterministic wave, 25 samples (0s..60s)
const TREND_POINTS = Array.from({ length: 25 }, (_, i) => {
  const t = i / 24;
  const y = 20 - 6 * Math.sin(t * Math.PI * 2.4) - 3 * Math.sin(t * Math.PI * 5.5 + 1);
  return `${t * 220},${y.toFixed(1)}`;
}).join(" ");

// ── Panel 4 platform capabilities ───────────────────────────────────────────
// Each entry maps to a real, wired part of the system (not marketing fiction):
// Zap → WebSocket streaming / low-latency pipeline, ScanSearch → GroundingDINO
// detection, Brain → GPT-4o chat engine, Eye → the 22-condition simulation set.
const FEATURES = [
  { icon: Zap, t: "Gerçek Zamanlı", d: "WebSocket ile düşük gecikmeli canlı akış" },
  { icon: ScanSearch, t: "Açık Kelime Tespiti", d: "GroundingDINO ile esnek nesne tanıma" },
  { icon: Brain, t: "AI Destekli", d: "GPT-4o klinik asistan entegrasyonu" },
  { icon: Eye, t: "22 Simülasyon", d: "Göz hastalığı simülasyonu" },
];

// The platform's real processing pipeline, camera to on-screen feedback.
const PIPELINE = [
  { t: "Kamera Girişi", d: "Canlı görüntü yakalama ve akış" },
  { t: "GroundingDINO Tespiti", d: "Açık kelime nesne tanıma" },
  { t: "Temporal Transformer", d: "Risk ve anomali analizi" },
  { t: "GPT-4o Klinik Yorum", d: "Yapay zeka destekli değerlendirme" },
  { t: "Gerçek Zamanlı Geri Bildirim", d: "Sonuçların anlık iletimi" },
];

// Mini sparkline point sets (viewBox 0 0 100 30)
const SPARK = {
  heart: "0,20 10,20 14,20 17,6 20,28 23,20 30,20 40,20 44,20 47,6 50,28 53,20 60,20 70,20 74,20 77,6 80,28 83,20 90,20 100,20",
  spo2: "0,18 10,14 20,17 30,10 40,15 50,9 60,14 70,11 80,16 90,10 100,13",
  bp: "0,15 10,20 20,12 30,18 40,11 50,17 60,10 70,16 80,12 90,19 100,14",
};

function MiniSparkline({ points }: { points: string }) {
  return (
    <svg viewBox="0 0 100 30" preserveAspectRatio="none" style={{ width: "100%", height: 26 }}>
      <polyline
        points={points}
        fill="none"
        stroke="#00D4FF"
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
        opacity={0.9}
      />
    </svg>
  );
}

const labelStyle: React.CSSProperties = {
  fontSize: 11,
  letterSpacing: "0.4em",
  color: "#00D4FF",
  textTransform: "uppercase",
  marginBottom: 24,
};

const headingStyle: React.CSSProperties = {
  fontSize: "clamp(3.5rem, 7vw, 6rem)",
  fontWeight: 900,
  lineHeight: 0.9,
  margin: 0,
};

const statCardStyle: React.CSSProperties = {
  background: "rgba(13,17,23,0.85)",
  border: "1px solid rgba(0,212,255,0.2)",
  borderRadius: 14,
  padding: "14px 16px",
  backdropFilter: "blur(8px)",
};

export default function CinematicSection() {
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("visible");
          }
        });
      },
      { threshold: 0.15 }
    );
    root.querySelectorAll(".reveal, .reveal-ecg").forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={rootRef}>
      <style>{`
        .cinematic-panel {
          min-height: 100vh;
          display: flex;
          align-items: center;
          position: relative;
          overflow: hidden;
        }
        .reveal {
          opacity: 0;
          transform: translateY(60px);
          transition: opacity 0.9s ease, transform 0.9s ease;
        }
        .reveal.visible {
          opacity: 1;
          transform: translateY(0);
        }
        .reveal-ecg.visible path {
          animation: ecgDraw 2.6s ease forwards, ecgPulse 2.8s ease-in-out 2.6s infinite;
        }
        @keyframes ecgPulse {
          0%, 100% { opacity: 0.55; }
          50% { opacity: 1; }
        }
        @keyframes focalPulse {
          0%, 100% { opacity: 0.55; transform: scale(0.9); }
          50% { opacity: 1; transform: scale(1.08); }
        }
        @keyframes orbitSpin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        @keyframes orbitSpinReverse {
          from { transform: rotate(0deg); }
          to { transform: rotate(-360deg); }
        }
        @keyframes ecgDraw {
          0% { stroke-dashoffset: 4000; }
          100% { stroke-dashoffset: 0; }
        }
        @keyframes scanLine {
          0% { top: 0%; opacity: 1; }
          100% { top: 100%; opacity: 0; }
        }
        @keyframes pulse-glow {
          0%, 100% { box-shadow: 0 0 20px rgba(0,212,255,0.3); }
          50% { box-shadow: 0 0 60px rgba(0,212,255,0.8); }
        }
        @keyframes eyeGlow {
          0%, 100% { filter: drop-shadow(0 0 20px rgba(0,212,255,0.22)); }
          50% { filter: drop-shadow(0 0 42px rgba(0,212,255,0.45)); }
        }
      `}</style>

      {/* ════════ PANEL 1 — GÖRMENİN YENİ BOYUTU ════════ */}
      <section
        className="cinematic-panel"
        style={{ background: "radial-gradient(ellipse at center, #0a1628 0%, #080B0F 70%)" }}
      >
        <div className="flex flex-col xl:flex-row items-center gap-10 xl:gap-8 w-full max-w-[1500px] mx-auto px-6 lg:px-10 py-20">
          {/* Text */}
          <div className="reveal xl:w-[36%] shrink-0" style={{ transitionDelay: "0.2s" }}>
            <p style={labelStyle}>ARGUS LENS — YAPAY ZEKA</p>
            <h2 style={{ ...headingStyle, color: "#F8FAFC" }}>GÖRMENİN</h2>
            <h2 style={{ ...headingStyle, color: "#00D4FF", margin: "0 0 32px 0" }}>
              YENİ BOYUTU
            </h2>
            <p
              style={{
                color: "#64748B",
                fontSize: "1.1rem",
                lineHeight: 1.7,
                maxWidth: 480,
                marginBottom: 40,
              }}
            >
              ArgusLens biyonik lens teknolojisiyle görüşünüzü yapay zeka destekli analiz
              ediyor. Gerçek zamanlı nesne tanıma, 22 göz hastalığı simülasyonu ve medikal
              AI asistan tek platformda.
            </p>
            <div className="flex gap-10">
              {[
                { n: "22", l: "Göz Hastalığı" },
                { n: "GPT-4o", l: "Vision Model" },
                { n: "<2s", l: "Analiz Süresi" },
              ].map((s) => (
                <div key={s.l}>
                  <p className="text-3xl font-extrabold text-cyan-400">{s.n}</p>
                  <p className="text-xs text-slate-500 mt-1">{s.l}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Photoreal eye — cropped hero photo with baked-in HUD scan overlay */}
          <div
            className="reveal flex-1 flex justify-center relative"
            style={{ transitionDelay: "0.4s" }}
          >
            <div
              className="relative w-[min(75vw,460px)]"
              style={{ aspectRatio: "440 / 574", animation: "eyeGlow 3.5s ease-in-out infinite" }}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/images/eye-hero.png"
                alt=""
                className="absolute inset-0 w-full h-full object-contain select-none pointer-events-none"
                draggable={false}
              />
              {/* Vertical scan sweep */}
              <div
                className="absolute left-0 w-full pointer-events-none"
                style={{
                  height: 2,
                  background: "linear-gradient(90deg, transparent, rgba(0,212,255,0.7), transparent)",
                  animation: "scanLine 3.2s ease-in-out infinite",
                }}
              />
            </div>
          </div>

          {/* Floating vitals stat column */}
          <div className="hidden xl:flex flex-col gap-4 w-[200px] shrink-0">
            <div className="reveal" style={{ ...statCardStyle, transitionDelay: "0.6s" }}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] text-slate-400 tracking-widest uppercase">Scanning</span>
                <span className="text-slate-600 text-xs">−</span>
              </div>
              <p className="text-xl font-extrabold text-cyan-400 mb-2">98%</p>
              <div className="h-1 rounded-full bg-slate-800 overflow-hidden">
                <div className="h-full rounded-full bg-cyan-400" style={{ width: "98%" }} />
              </div>
            </div>

            <div className="reveal" style={{ ...statCardStyle, transitionDelay: "0.7s" }}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] text-slate-400 tracking-widest uppercase">Heart Rate</span>
                <span className="text-slate-600 text-xs">×</span>
              </div>
              <p className="text-xl font-extrabold text-white mb-1">
                72 <span className="text-xs font-medium text-slate-500">BPM</span>
              </p>
              <MiniSparkline points={SPARK.heart} />
            </div>

            <div className="reveal" style={{ ...statCardStyle, transitionDelay: "0.8s" }}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] text-slate-400 tracking-widest uppercase">SpO2</span>
                <span className="text-slate-600 text-xs">×</span>
              </div>
              <p className="text-xl font-extrabold text-cyan-400 mb-1">98%</p>
              <MiniSparkline points={SPARK.spo2} />
            </div>

            <div className="reveal" style={{ ...statCardStyle, transitionDelay: "0.9s" }}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] text-slate-400 tracking-widest uppercase">Sistolik</span>
                <span className="text-slate-600 text-xs">×</span>
              </div>
              <p className="text-xl font-extrabold text-white mb-1">
                122 <span className="text-xs font-medium text-slate-500">mmHg</span>
              </p>
              <MiniSparkline points={SPARK.bp} />
            </div>

            <div className="reveal" style={{ ...statCardStyle, transitionDelay: "1.0s" }}>
              <span className="text-[10px] text-slate-400 tracking-widest uppercase">AI Analiz</span>
              <p className="text-lg font-extrabold text-cyan-400 mt-1 mb-2">Aktif</p>
              <div className="flex items-center gap-1">
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="size-1.5 rounded-full bg-cyan-400"
                    style={{ animation: `typingDot 1.2s ease-in-out ${i * 0.2}s infinite` }}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ════════ PANEL 2 — AI GÖZÜNÜZ DEVREDE ════════ */}
      <section className="cinematic-panel" style={{ background: "#080B0F" }}>
        <div className="flex flex-col lg:flex-row items-center gap-12 w-full max-w-7xl mx-auto px-6 py-20">
          {/* Photoreal eye — real photo with live-style detection overlay */}
          <div className="reveal lg:w-1/2 flex justify-center order-2 lg:order-1" style={{ transitionDelay: "0.3s" }}>
            <div
              className="relative"
              style={{ width: "min(70vw,420px)", aspectRatio: "440 / 574", animation: "eyeGlow 4s ease-in-out infinite" }}
            >
              <svg viewBox="0 0 440 574" className="w-full h-full block overflow-visible">
                <image href="/images/eye-detection.png" x="0" y="0" width="440" height="574" preserveAspectRatio="xMidYMid slice" />

                {/* Crosshair + scan rings centered on the iris */}
                <line x1="205" y1="18" x2="205" y2="556" stroke="rgba(0,212,255,0.2)" strokeWidth="1" strokeDasharray="4 6" />
                <line x1="18" y1="250" x2="422" y2="250" stroke="rgba(0,212,255,0.2)" strokeWidth="1" strokeDasharray="4 6" />
                <circle cx="205" cy="250" r="60" fill="none" stroke="rgba(0,212,255,0.3)" strokeDasharray="2 5" />
                <circle cx="205" cy="250" r="92" fill="none" stroke="rgba(0,212,255,0.15)" />

                {/* Corner brackets */}
                <path d="M14,44 L14,14 L44,14" stroke="#00D4FF" strokeWidth="2" fill="none" opacity={0.7} />
                <path d="M396,14 L426,14 L426,44" stroke="#00D4FF" strokeWidth="2" fill="none" opacity={0.7} />
                <path d="M426,530 L426,560 L396,560" stroke="#00D4FF" strokeWidth="2" fill="none" opacity={0.7} />
                <path d="M44,560 L14,560 L14,530" stroke="#00D4FF" strokeWidth="2" fill="none" opacity={0.7} />

                {/* Detection cards, each with a leader line to a point on the eye */}
                {DETECTION_CARDS.map((c) => (
                  <g key={c.key}>
                    <line x1={c.anchor[0]} y1={c.anchor[1]} x2={c.edge[0]} y2={c.edge[1]} stroke="#00D4FF" strokeWidth="1" strokeDasharray="2 3" opacity={0.55} />
                    <circle cx={c.anchor[0]} cy={c.anchor[1]} r={3} fill="#00D4FF" opacity={0.85} />
                    <rect x={c.x} y={c.y} width={c.w} height={c.h} rx={4} fill="rgba(5,10,15,0.82)" stroke="#00D4FF" strokeWidth="1" opacity={0.6} />
                    <text x={c.x + 10} y={c.y + 20} fill="#00D4FF" fontSize="11" fontWeight="bold" fontFamily="monospace">{c.label}</text>
                    <text x={c.x + 10} y={c.y + 36} fill="#CBD5E1" fontSize="10" fontFamily="monospace">{c.conf}</text>
                    <g transform={`translate(${c.x + c.w / 2 - 22}, ${c.y + 48})`}>{DETECTION_ICONS[c.icon]}</g>
                  </g>
                ))}
              </svg>
              {/* Scan sweep */}
              <div
                className="absolute left-0 w-full pointer-events-none"
                style={{
                  height: 2,
                  background: "linear-gradient(90deg, transparent, rgba(0,212,255,0.7), transparent)",
                  animation: "scanLine 2.8s ease-in-out infinite",
                }}
              />
            </div>
          </div>

          {/* Text */}
          <div className="reveal lg:w-1/2 order-1 lg:order-2" style={{ transitionDelay: "0.1s" }}>
            <p style={labelStyle}>NESNE TESPİTİ</p>
            <h2 style={{ ...headingStyle, color: "#F8FAFC" }}>AI GÖZÜNÜZ</h2>
            <h2 style={{ ...headingStyle, color: "#00D4FF", margin: "0 0 32px 0" }}>DEVREDE</h2>
            <p style={{ color: "#64748B", fontSize: "1.1rem", lineHeight: 1.7, maxWidth: 480, marginBottom: 32 }}>
              GroundingDINO açık-kelime tespit modeliyle görüntüdeki nesneleri
              gerçek zamanlı olarak analiz ediyor.
            </p>
            <ul style={{ color: "#94A3B8", fontSize: "0.95rem", lineHeight: 2, listStyle: "none", padding: 0, margin: 0 }}>
              <li><span className="text-cyan-400">●</span> Türkçe &amp; İngilizce nesne tanıma</li>
              <li><span className="text-cyan-400">●</span> Açık kelime dağarcığıyla esnek tespit</li>
              <li><span className="text-cyan-400">●</span> Gerçek zamanlı bounding box</li>
              <li><span className="text-cyan-400">●</span> Çoklu nesne aynı anda tespiti</li>
            </ul>
          </div>
        </div>
      </section>

      {/* ════════ PANEL 3 — YAŞAM BELİRTELERİ ════════ */}
      <section className="cinematic-panel" style={{ background: "#080B0F" }}>
        {/* Full-width ECG line — thin neon trace with a continuous soft pulse */}
        <svg
          className="reveal-ecg"
          viewBox="0 0 1600 100"
          preserveAspectRatio="none"
          style={{ position: "absolute", top: "68%", left: 0, width: "100%", height: 100, opacity: 0.28 }}
        >
          <defs>
            <filter id="ecgNeon" x="-20%" y="-200%" width="140%" height="500%">
              <feGaussianBlur stdDeviation="2.2" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          <path
            d={ECG_PATH}
            stroke="#00D4FF"
            strokeWidth="1"
            fill="none"
            strokeDasharray="4000"
            strokeDashoffset="4000"
            filter="url(#ecgNeon)"
          />
        </svg>

        <div className="reveal w-full max-w-6xl mx-auto px-6 py-20 relative flex flex-col xl:flex-row items-center gap-14" style={{ transitionDelay: "0.2s" }}>
          <div className="flex-1 text-center xl:text-left">
            <p style={labelStyle}>VİTAL İZLEME</p>
            <h2 style={{ ...headingStyle, margin: "0 0 20px 0" }}>
              <span style={{ color: "#F8FAFC" }}>YAŞAM</span>{" "}
              <span style={{ color: "#00D4FF" }}>BELİRTELERİ</span>
            </h2>

            {/* Status badge */}
            <div className="flex justify-center xl:justify-start mb-6">
              <span
                className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full text-[11px] tracking-widest uppercase font-semibold"
                style={{ border: "1px solid rgba(0,212,255,0.25)", background: "rgba(0,212,255,0.06)", color: "#00D4FF" }}
              >
                AI Monitoring
                <span style={{ color: "#334155" }}>•</span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="size-1.5 rounded-full bg-cyan-400 animate-pulse" />
                  LIVE
                </span>
                <span style={{ color: "#334155" }}>•</span>
                <span style={{ color: "#94A3B8", fontWeight: 500 }}>Temporal Transformer</span>
              </span>
            </div>

            <p style={{ color: "#64748B", fontSize: "1.1rem", lineHeight: 1.7, maxWidth: 560 }} className="mx-auto xl:mx-0">
              Nabız, SpO2, kan basıncı ve göz içi basıncını anlık olarak izle. AI destekli
              risk analizi ile olağandışı değerleri anında tespit et.
            </p>

            <div className="flex flex-wrap justify-center xl:justify-start gap-5 mt-12">
              {VITAL_CARDS.map((c) => (
                <div
                  key={c.l}
                  className="card-lift"
                  style={{
                    background: "linear-gradient(135deg, rgba(13,17,23,0.92), rgba(17,24,39,0.92))",
                    border: "1px solid rgba(0,212,255,0.15)",
                    borderRadius: 16,
                    padding: "20px 26px",
                    textAlign: "center",
                    minWidth: 168,
                  }}
                >
                  <c.icon className="size-4 text-cyan-400/80 mx-auto mb-2" strokeWidth={1.75} />
                  <p className="text-3xl font-extrabold text-cyan-400">{c.n}</p>
                  <p className="text-xs text-slate-500 tracking-widest mt-2">{c.l}</p>
                  <p className="text-xs mt-1 text-slate-500">
                    {c.s.startsWith("●") ? <span className="text-cyan-400">{c.s}</span> : c.s}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* Floating 60-second live trend */}
          <div
            className="reveal hidden xl:block shrink-0 w-[260px]"
            style={{ ...statCardStyle, transitionDelay: "0.5s" }}
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-[10px] text-slate-400 tracking-widest uppercase">Son 60 Saniye</span>
              <span className="inline-flex items-center gap-1 text-[9px] font-bold tracking-widest text-cyan-400">
                <span className="size-1.5 rounded-full bg-cyan-400 animate-pulse" />
                CANLI
              </span>
            </div>
            <svg viewBox="0 0 220 40" preserveAspectRatio="none" style={{ width: "100%", height: 60 }}>
              <polyline
                points={TREND_POINTS}
                fill="none"
                stroke="#00D4FF"
                strokeWidth={1.5}
                strokeLinejoin="round"
                strokeLinecap="round"
              />
            </svg>
            <div className="flex justify-between text-[9px] text-slate-600 mt-1 mb-3">
              <span>-60s</span>
              <span>-40s</span>
              <span>-20s</span>
              <span>şimdi</span>
            </div>
            <div className="flex items-baseline justify-between border-t border-[rgba(255,255,255,0.06)] pt-3">
              <span className="text-xs text-slate-500">Nabız</span>
              <span className="text-lg font-extrabold text-cyan-400">
                74 <span className="text-xs font-medium text-slate-500">bpm</span>
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* ════════ PANEL 4 — BİYONİK LENS ════════ */}
      <section
        className="cinematic-panel"
        style={{ background: "radial-gradient(ellipse at right, #0a1628 0%, #080B0F 60%)" }}
      >
        <div className="w-full max-w-7xl mx-auto px-6 py-20 flex flex-col gap-10">
          <div className="flex flex-col lg:flex-row items-center gap-12">
            {/* Lens cross-section + capability chips */}
            <div className="reveal lg:w-1/2 flex flex-col items-center gap-8" style={{ transitionDelay: "0.4s" }}>
              <div className="relative w-[min(70vw,420px)]" style={{ animation: "eyeGlow 3.5s ease-in-out infinite" }}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src="/images/lens-diagram.png"
                  alt="Biyonik lens kesiti — kornea, lens ve retina katmanları"
                  className="w-full h-auto select-none pointer-events-none"
                  draggable={false}
                />
              </div>

              <div className="grid grid-cols-2 xl:grid-cols-4 gap-3 w-full">
                {FEATURES.map((f) => (
                  <div
                    key={f.t}
                    className="card-lift"
                    style={{
                      background: "linear-gradient(135deg, rgba(13,17,23,0.9), rgba(17,24,39,0.9))",
                      border: "1px solid rgba(0,212,255,0.15)",
                      borderRadius: 14,
                      padding: "16px 10px",
                      textAlign: "center",
                    }}
                  >
                    <f.icon className="size-5 text-cyan-400 mx-auto mb-2" strokeWidth={1.75} />
                    <p className="text-[11px] font-bold text-slate-100 uppercase tracking-wide leading-tight">{f.t}</p>
                    <p className="text-[10px] text-slate-500 mt-1 leading-snug">{f.d}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Text + feature rows + pipeline */}
            <div className="reveal lg:w-1/2" style={{ transitionDelay: "0.1s" }}>
              <p style={labelStyle}>GÖRÜŞÜN GELECEĞİ</p>
              <h2 style={{ ...headingStyle, color: "#F8FAFC" }}>BİYONİK</h2>
              <h2 style={{ ...headingStyle, color: "#00D4FF", margin: "0 0 24px 0" }}>LENS</h2>
              <p style={{ color: "#64748B", fontSize: "1.1rem", lineHeight: 1.7, maxWidth: 480, marginBottom: 24 }}>
                Doğal mercek işlevini taklit eden gelişmiş optik sistem. Yapay zeka ile
                optimize edilen görüş kalitesi.
              </p>

              <div className="grid sm:grid-cols-2 gap-8">
                <div>
                  {FEATURES.map((f) => (
                    <div key={f.t} className="flex items-center gap-4 py-3 border-b border-[rgba(255,255,255,0.05)] last:border-0">
                      <span className="size-10 rounded-lg bg-cyan-500/10 flex items-center justify-center shrink-0">
                        <f.icon className="size-[18px] text-cyan-400" strokeWidth={1.75} />
                      </span>
                      <div>
                        <p className="text-sm font-bold text-slate-100 m-0">{f.t}</p>
                        <p className="text-xs text-slate-500 m-0">{f.d}</p>
                      </div>
                    </div>
                  ))}
                </div>

                <div
                  style={{
                    border: "1px solid rgba(0,212,255,0.2)",
                    borderRadius: 16,
                    padding: "20px 20px",
                    background: "rgba(13,17,23,0.6)",
                  }}
                >
                  <p className="text-xs font-bold text-cyan-400 uppercase tracking-widest mb-4">AI Analiz Hattı</p>
                  {PIPELINE.map((p, i) => (
                    <div key={p.t} className="flex gap-3 mb-4 last:mb-0">
                      <span className="shrink-0 size-5 rounded-full border border-cyan-500/40 text-cyan-400 text-[10px] font-bold flex items-center justify-center mt-0.5">
                        {i + 1}
                      </span>
                      <div>
                        <p className="text-xs font-bold text-slate-100 m-0">{p.t}</p>
                        <p className="text-[11px] text-slate-500 m-0 leading-snug">{p.d}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* System status bar */}
          <div
            className="reveal flex flex-wrap items-center justify-between gap-6"
            style={{
              ...statCardStyle,
              padding: "18px 28px",
              transitionDelay: "0.6s",
            }}
          >
            <div className="flex items-center gap-3">
              <ShieldCheck className="size-5 text-cyan-400" strokeWidth={1.75} />
              <div>
                <p className="text-xs font-bold text-slate-200 uppercase tracking-widest m-0">Sistem Durumu</p>
                <p className="text-xs text-slate-500 m-0">Tüm servisler aktif ve çalışır durumda</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right">
                <p className="text-[10px] text-cyan-400 uppercase tracking-widest m-0">Performans</p>
                <p className="text-2xl font-extrabold text-cyan-400 m-0">%98</p>
              </div>
              <div style={{ width: 100 }}>
                <MiniSparkline points={SPARK.spo2} />
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
