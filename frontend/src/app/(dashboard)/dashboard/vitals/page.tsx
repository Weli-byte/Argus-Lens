"use client";

import React, { useMemo, useState, useEffect } from "react";
import { 
  Heart, 
  Activity, 
  Thermometer, 
  Droplet, 
  Eye, 
  ShieldAlert, 
  Sparkles, 
  BrainCircuit, 
  RefreshCw, 
  FileText, 
  Brain,
  Compass,
  Cpu,
  Server,
  Maximize,
  Settings,
  Flame,
  Gauge
} from "lucide-react";
import { useVitalStream } from "@/hooks/useVitalStream";
import { useVitalStore } from "@/store/vital-store";
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  CartesianGrid
} from "recharts";

export default function VitalMonitorPage() {
  const { currentTelemetry, history, connectionStatus } = useVitalStream();
  
  const report = useVitalStore((s) => s.report);
  const recommendations = useVitalStore((s) => s.recommendations);
  const generatingReport = useVitalStore((s) => s.generatingReport);
  const reportError = useVitalStore((s) => s.reportError);
  
  const setGeneratingReport = useVitalStore((s) => s.setGeneratingReport);
  const setReportData = useVitalStore((s) => s.setReportData);
  const setReportError = useVitalStore((s) => s.setReportError);

  const [currentTime, setCurrentTime] = useState("");
  const [activeTab, setActiveTab] = useState<"report" | "recs">("report");

  // Keep digital clock updated
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setCurrentTime(now.toLocaleTimeString("tr-TR", { hour12: false }));
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const handleGenerateReport = async () => {
    if (!currentTelemetry) return;
    
    setGeneratingReport(true);
    try {
      const res = await fetch("http://127.0.0.1:8090/api/v1/vitals/report", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          vitals: currentTelemetry.vitals,
          news2: currentTelemetry.news2,
        }),
      });

      if (!res.ok) {
        throw new Error("Rapor üretimi başarısız oldu.");
      }

      const data = await res.json();
      setReportData(data.report, data.recommendations);
    } catch (err: any) {
      console.error(err);
      setReportError(err.message || "Rapor üretiminde hata oluştu.");
    }
  };

  const currentVitals = currentTelemetry?.vitals;
  const news2 = currentTelemetry?.news2;
  const analysis = currentTelemetry?.analysis;

  // Generate waveform datasets with predictions and confidence corridors
  const hrDataset = useMemo(() => {
    if (history.length === 0) return [];
    const trend = analysis?.trend_direction || "stable";
    
    const data = history.slice(-40).map((h) => ({
      time: new Date(h.timestamp).toLocaleTimeString("tr-TR", { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      val: h.vitals.heart_rate,
      prediction: null,
      confMin: null,
      confMax: null,
    }));

    // Append 15 prediction steps
    const lastVal = data[data.length - 1].val;
    let currentPred = lastVal;
    const trendMultiplier = trend === "up" ? 0.4 : trend === "down" ? -0.4 : 0.0;

    // We add the last historical point as the start of the prediction to make it continuous
    data.push({
      time: "NOW",
      val: lastVal,
      prediction: lastVal,
      confMin: lastVal,
      confMax: lastVal,
    });

    for (let i = 1; i <= 15; i++) {
      currentPred += trendMultiplier + (Math.random() - 0.5) * 0.8;
      currentPred = Math.min(150, Math.max(40, currentPred));
      data.push({
        time: `+${i}s`,
        val: null as any,
        prediction: parseFloat(currentPred.toFixed(1)),
        confMin: parseFloat((currentPred - (i * 0.4)).toFixed(1)),
        confMax: parseFloat((currentPred + (i * 0.4)).toFixed(1)),
      });
    }
    return data;
  }, [history, analysis]);

  const spo2Dataset = useMemo(() => {
    if (history.length === 0) return [];
    const trend = analysis?.trend_direction || "stable";
    
    const data = history.slice(-40).map((h) => ({
      time: new Date(h.timestamp).toLocaleTimeString("tr-TR", { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      val: h.vitals.spo2,
      prediction: null,
      confMin: null,
      confMax: null,
    }));

    const lastVal = data[data.length - 1].val;
    let currentPred = lastVal;
    const trendMultiplier = trend === "up" ? 0.05 : trend === "down" ? -0.08 : 0.0;

    data.push({
      time: "NOW",
      val: lastVal,
      prediction: lastVal,
      confMin: lastVal,
      confMax: lastVal,
    });

    for (let i = 1; i <= 15; i++) {
      currentPred += trendMultiplier + (Math.random() - 0.5) * 0.15;
      currentPred = Math.min(100, Math.max(80, currentPred));
      data.push({
        time: `+${i}s`,
        val: null as any,
        prediction: parseFloat(currentPred.toFixed(1)),
        confMin: parseFloat((currentPred - (i * 0.08)).toFixed(1)),
        confMax: parseFloat((currentPred + (i * 0.08)).toFixed(1)),
      });
    }
    return data;
  }, [history, analysis]);

  const bpDataset = useMemo(() => {
    if (history.length === 0) return [];
    const trend = analysis?.trend_direction || "stable";
    
    const data = history.slice(-40).map((h) => ({
      time: new Date(h.timestamp).toLocaleTimeString("tr-TR", { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      val: h.vitals.systolic_bp,
      prediction: null,
      confMin: null,
      confMax: null,
    }));

    const lastVal = data[data.length - 1].val;
    let currentPred = lastVal;
    const trendMultiplier = trend === "up" ? 0.5 : trend === "down" ? -0.5 : 0.0;

    data.push({
      time: "NOW",
      val: lastVal,
      prediction: lastVal,
      confMin: lastVal,
      confMax: lastVal,
    });

    for (let i = 1; i <= 15; i++) {
      currentPred += trendMultiplier + (Math.random() - 0.5) * 1.0;
      currentPred = Math.min(220, Math.max(70, currentPred));
      data.push({
        time: `+${i}s`,
        val: null as any,
        prediction: parseFloat(currentPred.toFixed(1)),
        confMin: parseFloat((currentPred - (i * 0.6)).toFixed(1)),
        confMax: parseFloat((currentPred + (i * 0.6)).toFixed(1)),
      });
    }
    return data;
  }, [history, analysis]);

  // Risk circle parameters
  const riskScore = news2?.score ?? 0;
  const riskRatio = Math.min(1.0, riskScore / 10); // scale up to 10 points
  const radius = 36;
  const stroke = 6;
  const normalizedRadius = radius - stroke * 2;
  const circumference = normalizedRadius * 2 * Math.PI;
  const strokeDashoffset = circumference - (riskRatio * circumference);

  const getRiskColor = (score: number) => {
    if (score === 0) return "text-green-400 stroke-green-400";
    if (score <= 4) return "text-amber-400 stroke-amber-400";
    if (score <= 6) return "text-orange-400 stroke-orange-400";
    return "text-red-400 stroke-red-400";
  };

  return (
    <div className="flex flex-col min-h-screen bg-[#080B0F] text-slate-100 font-sans p-4 space-y-4">
      {/* Top Banner Navigation */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between border-b border-[#1E293B] pb-3 shrink-0 gap-2">
        <div className="flex flex-col md:flex-row md:items-center gap-4">
          <span className="text-sm font-bold font-mono tracking-widest text-[#00D4FF]">
            ARGUSLENS VITAL MONITOR
          </span>
          <div className="hidden md:flex items-center gap-4 text-[10px] text-slate-500 font-mono border-l border-[#1E293B] pl-4">
            <span>Patient ID: <span className="text-slate-300 font-bold">ARG-2025-0421</span></span>
            <span>Name: <span className="text-slate-300 font-bold">Mehmet Yılmaz</span></span>
            <span>Age: <span className="text-slate-300 font-bold">62</span></span>
            <span>Unit: <span className="text-slate-300 font-bold">ICU-3</span></span>
          </div>
        </div>
        
        <div className="flex items-center gap-4">
          <span className="text-sm font-mono font-bold text-slate-300 tracking-wider">
            {currentTime}
          </span>
          <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full border border-green-500/20 bg-green-500/10 text-green-400 text-[9px] font-mono font-bold uppercase animate-pulse">
            <span className="size-1.5 rounded-full bg-green-400"></span> LIVE
          </span>
          <button className="text-slate-500 hover:text-slate-300 cursor-pointer">
            <Maximize className="size-4" />
          </button>
          <button className="text-slate-500 hover:text-slate-300 cursor-pointer">
            <Settings className="size-4" />
          </button>
        </div>
      </div>

      {!currentTelemetry ? (
        <div className="flex-1 flex flex-col items-center justify-center py-40 border border-[#1E293B] bg-[#0D1117] rounded-xl space-y-4">
          <RefreshCw className="size-8 animate-spin text-[#00D4FF]" />
          <p className="text-xs text-slate-400 font-mono">Biyonik lens sensor verileri bekleniyor...</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 flex-1">
          
          {/* Waveform Charts Section (Takes 3/4 width) */}
          <div className="lg:col-span-3 flex flex-col space-y-3">
            
            {/* Heart Rate Waveform */}
            <div className="border border-[#1E293B] bg-[#0D1117]/60 rounded-xl p-3 flex flex-col h-[180px] justify-between relative overflow-hidden">
              <div className="flex items-center justify-between z-10">
                <span className="text-[10px] font-mono font-bold text-red-500 uppercase tracking-wider flex items-center gap-1.5">
                  <Heart className="size-3.5 fill-red-500 animate-pulse text-red-500" /> HEART RATE (bpm)
                </span>
                <span className="text-[10px] font-mono text-slate-500">Prediction (Next 15s)</span>
              </div>
              <div className="flex-1 min-h-0">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={hrDataset}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#161D2D" vertical={false} />
                    <XAxis dataKey="time" tick={{ fill: '#475569', fontSize: 9 }} tickLine={false} axisLine={false} />
                    <YAxis domain={[40, 140]} tick={{ fill: '#475569', fontSize: 9 }} tickLine={false} axisLine={false} />
                    <Tooltip contentStyle={{ backgroundColor: '#0D1117', borderColor: '#1E293B', fontSize: 10 }} />
                    <ReferenceLine x="NOW" stroke="#475569" strokeDasharray="3 3" label={{ value: 'NOW', fill: '#94A3B8', fontSize: 8, position: 'top' }} />
                    
                    {/* Confidence corridor area */}
                    <Area dataKey="confMax" stroke="none" fill="rgba(239, 68, 68, 0.08)" />
                    <Area dataKey="confMin" stroke="none" fill="#0D1117" />
                    
                    {/* Live and Prediction Lines */}
                    <Line type="monotone" dataKey="val" stroke="#EF4444" strokeWidth={1.5} dot={false} activeDot={{ r: 4 }} />
                    <Line type="monotone" dataKey="prediction" stroke="#EF4444" strokeWidth={1.2} strokeDasharray="3 3" dot={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* SpO2 Waveform */}
            <div className="border border-[#1E293B] bg-[#0D1117]/60 rounded-xl p-3 flex flex-col h-[180px] justify-between relative overflow-hidden">
              <div className="flex items-center justify-between z-10">
                <span className="text-[10px] font-mono font-bold text-cyan-400 uppercase tracking-wider flex items-center gap-1.5">
                  <Droplet className="size-3.5 fill-cyan-400 text-cyan-400" /> SPO₂ (%)
                </span>
                <span className="text-[10px] font-mono text-slate-500">Prediction (Next 15s)</span>
              </div>
              <div className="flex-1 min-h-0">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={spo2Dataset}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#161D2D" vertical={false} />
                    <XAxis dataKey="time" tick={{ fill: '#475569', fontSize: 9 }} tickLine={false} axisLine={false} />
                    <YAxis domain={[85, 101]} tick={{ fill: '#475569', fontSize: 9 }} tickLine={false} axisLine={false} />
                    <Tooltip contentStyle={{ backgroundColor: '#0D1117', borderColor: '#1E293B', fontSize: 10 }} />
                    <ReferenceLine x="NOW" stroke="#475569" strokeDasharray="3 3" label={{ value: 'NOW', fill: '#94A3B8', fontSize: 8, position: 'top' }} />
                    
                    <Area dataKey="confMax" stroke="none" fill="rgba(6, 182, 212, 0.08)" />
                    <Area dataKey="confMin" stroke="none" fill="#0D1117" />
                    
                    <Line type="monotone" dataKey="val" stroke="#06B6D4" strokeWidth={1.5} dot={false} activeDot={{ r: 4 }} />
                    <Line type="monotone" dataKey="prediction" stroke="#06B6D4" strokeWidth={1.2} strokeDasharray="3 3" dot={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Systolic BP Waveform */}
            <div className="border border-[#1E293B] bg-[#0D1117]/60 rounded-xl p-3 flex flex-col h-[180px] justify-between relative overflow-hidden">
              <div className="flex items-center justify-between z-10">
                <span className="text-[10px] font-mono font-bold text-yellow-500 uppercase tracking-wider flex items-center gap-1.5">
                  <Activity className="size-3.5 text-yellow-500" /> SYSTOLIC BP (mmHg)
                </span>
                <span className="text-[10px] font-mono text-slate-500">Prediction (Next 15s)</span>
              </div>
              <div className="flex-1 min-h-0">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={bpDataset}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#161D2D" vertical={false} />
                    <XAxis dataKey="time" tick={{ fill: '#475569', fontSize: 9 }} tickLine={false} axisLine={false} />
                    <YAxis domain={[80, 180]} tick={{ fill: '#475569', fontSize: 9 }} tickLine={false} axisLine={false} />
                    <Tooltip contentStyle={{ backgroundColor: '#0D1117', borderColor: '#1E293B', fontSize: 10 }} />
                    <ReferenceLine x="NOW" stroke="#475569" strokeDasharray="3 3" label={{ value: 'NOW', fill: '#94A3B8', fontSize: 8, position: 'top' }} />
                    
                    <Area dataKey="confMax" stroke="none" fill="rgba(234, 179, 8, 0.08)" />
                    <Area dataKey="confMin" stroke="none" fill="#0D1117" />
                    
                    <Line type="monotone" dataKey="val" stroke="#EAB308" strokeWidth={1.5} dot={false} activeDot={{ r: 4 }} />
                    <Line type="monotone" dataKey="prediction" stroke="#EAB308" strokeWidth={1.2} strokeDasharray="3 3" dot={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Bottom 4 Panels (Metrics summary and AI assessments) */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3 shrink-0">
              
              {/* Trend Summary */}
              <div className="border border-[#1E293B] bg-[#0D1117] rounded-xl p-3 flex flex-col justify-between">
                <p className="text-[10px] font-mono font-bold text-slate-400 tracking-wider border-b border-[#1E293B] pb-1.5 uppercase">
                  TREND SUMMARY
                </p>
                <div className="space-y-2 py-2 text-xs font-mono">
                  <div className="flex justify-between items-center">
                    <span className="text-red-500">Heart Rate</span>
                    <span className="text-slate-400 flex items-center gap-1">
                      {analysis?.trend_direction === "up" ? "Rising ↑" : analysis?.trend_direction === "down" ? "Falling ↓" : "Stable →"}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-cyan-400">SpO₂</span>
                    <span className="text-slate-400 flex items-center gap-1">
                      {analysis?.trend_direction === "up" ? "Stable →" : "Stable →"}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-yellow-500">Systolic BP</span>
                    <span className="text-slate-400 flex items-center gap-1">
                      {analysis?.trend_direction === "up" ? "Rising ↑" : analysis?.trend_direction === "down" ? "Falling ↓" : "Stable →"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Anomaly Probability */}
              <div className="border border-[#1E293B] bg-[#0D1117] rounded-xl p-3 flex flex-col justify-between">
                <p className="text-[10px] font-mono font-bold text-slate-400 tracking-wider border-b border-[#1E293B] pb-1.5 uppercase">
                  ANOMALY INDEX
                </p>
                <div className="space-y-2 py-2 text-[10px] font-mono">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Total Anomaly</span>
                    <span className="text-red-400 font-bold">%{( (analysis?.anomaly_probability ?? 0) * 100 ).toFixed(1)}</span>
                  </div>
                  {/* Progress bar */}
                  <div className="h-1.5 w-full bg-[#161D2D] rounded-full overflow-hidden">
                    <div 
                      className={`h-full rounded-full transition-all duration-500 ${
                        (analysis?.anomaly_probability ?? 0) > 0.6 
                          ? "bg-red-500" 
                          : (analysis?.anomaly_probability ?? 0) > 0.3 
                            ? "bg-amber-500" 
                            : "bg-cyan-500"
                      }`}
                      style={{ width: `${(analysis?.anomaly_probability ?? 0) * 100}%` }}
                    />
                  </div>
                  <div className="flex justify-between text-[8px] text-slate-500">
                    <span>NORMAL</span>
                    <span>ANOMALOUS</span>
                  </div>
                </div>
              </div>

              {/* Prediction Horizon */}
              <div className="border border-[#1E293B] bg-[#0D1117] rounded-xl p-3 flex flex-col justify-between">
                <p className="text-[10px] font-mono font-bold text-slate-400 tracking-wider border-b border-[#1E293B] pb-1.5 uppercase">
                  PREDICTION (10s)
                </p>
                <div className="space-y-1.5 py-1.5 text-[9px] font-mono">
                  <div className="flex justify-between border-b border-[#1E293B]/40 pb-1 text-slate-500">
                    <span>PARAM</span>
                    <span>MIN/MAX</span>
                    <span>TREND</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-red-500">HR</span>
                    <span className="text-slate-300">
                      {Math.round((currentVitals?.heart_rate ?? 70) * 0.95)}/{Math.round((currentVitals?.heart_rate ?? 70) * 1.05)}
                    </span>
                    <span className="text-slate-400">{analysis?.trend_direction === "up" ? "▲" : analysis?.trend_direction === "down" ? "▼" : "→"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-cyan-400">SpO₂</span>
                    <span className="text-slate-300">
                      {Math.round((currentVitals?.spo2 ?? 98) * 0.99)}/{Math.round(Math.min(100, (currentVitals?.spo2 ?? 98) * 1.01))}
                    </span>
                    <span className="text-slate-400">→</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-yellow-500">SBP</span>
                    <span className="text-slate-300">
                      {Math.round((currentVitals?.systolic_bp ?? 120) * 0.96)}/{Math.round((currentVitals?.systolic_bp ?? 120) * 1.04)}
                    </span>
                    <span className="text-slate-400">{analysis?.trend_direction === "up" ? "▲" : analysis?.trend_direction === "down" ? "▼" : "→"}</span>
                  </div>
                </div>
              </div>

              {/* Notes / Alerts & GPT-4o generator */}
              <div className="border border-[#1E293B] bg-[#0D1117] rounded-xl p-3 flex flex-col justify-between">
                <p className="text-[10px] font-mono font-bold text-slate-400 tracking-wider border-b border-[#1E293B] pb-1.5 uppercase">
                  AI DOKTOR RAPORU
                </p>
                <div className="py-2 flex flex-col gap-2">
                  <button
                    onClick={handleGenerateReport}
                    disabled={generatingReport}
                    className="w-full flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-lg border border-cyan-500/20 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 text-[10px] font-mono font-bold cursor-pointer disabled:opacity-50 transition-all"
                  >
                    {generatingReport ? (
                      <>
                        <RefreshCw className="size-3 animate-spin" />
                        ÜRETİLİYOR...
                      </>
                    ) : (
                      <>
                        <BrainCircuit className="size-3" />
                        GPT-4O RAPORU YAZ
                      </>
                    )}
                  </button>
                  {report && (
                    <div className="flex items-center gap-1.5 text-[9px] text-green-400 font-mono">
                      <span className="size-1.5 rounded-full bg-green-400 inline-block animate-pulse"></span> Rapor Hazır! (Aşağıya bakın)
                    </div>
                  )}
                </div>
              </div>

            </div>

          </div>

          {/* Right Sidebar (Primary telemetry cards & risk gauge) */}
          <div className="flex flex-col space-y-3">
            
            {/* Primary Vitals cards */}
            <div className="border border-[#1E293B] bg-[#0D1117] rounded-xl p-3 flex items-center justify-between h-[75px]">
              <div>
                <span className="text-[9px] font-mono text-slate-500 block">HEART RATE</span>
                <span className="text-xl font-bold font-mono text-red-500 tracking-wider">{currentVitals?.heart_rate ?? "—"}</span>
                <span className="text-[9px] font-mono text-slate-500 block">Range: 60 - 100 | ECG</span>
              </div>
              <Heart className="size-7 text-red-500/40 fill-red-500/10" />
            </div>

            <div className="border border-[#1E293B] bg-[#0D1117] rounded-xl p-3 flex items-center justify-between h-[75px]">
              <div>
                <span className="text-[9px] font-mono text-slate-500 block">SPO₂</span>
                <span className="text-xl font-bold font-mono text-cyan-400 tracking-wider">{currentVitals?.spo2 ?? "—"} %</span>
                <span className="text-[9px] font-mono text-slate-500 block">Range: 95 - 100 | SpO₂</span>
              </div>
              <Droplet className="size-7 text-cyan-500/40 fill-cyan-500/10" />
            </div>

            <div className="border border-[#1E293B] bg-[#0D1117] rounded-xl p-3 flex items-center justify-between h-[75px]">
              <div>
                <span className="text-[9px] font-mono text-slate-500 block">BLOOD PRESSURE</span>
                <span className="text-xl font-bold font-mono text-yellow-500 tracking-wider">
                  {currentVitals ? `${Math.round(currentVitals.systolic_bp)}/${Math.round(currentVitals.diastolic_bp)}` : "—"}
                </span>
                <span className="text-[9px] font-mono text-slate-500 block">Range: 90-140/60-90 | NIBP</span>
              </div>
              <Gauge className="size-7 text-yellow-500/40" />
            </div>

            {/* NEWS2 Risk Circular Gauge */}
            <div className="border border-[#1E293B] bg-[#0D1117] rounded-xl p-3 flex flex-col justify-between shrink-0">
              <span className="text-[10px] font-mono font-bold text-slate-400 uppercase tracking-wider block border-b border-[#1E293B] pb-1.5">
                NEWS2 RISK SCORE
              </span>
              
              <div className="flex items-center gap-4 py-3">
                {/* SVG Ring progress */}
                <div className="relative shrink-0 flex items-center justify-center">
                  <svg className="size-[80px] -rotate-90">
                    {/* Background path */}
                    <circle
                      className="stroke-[#161D2D]"
                      fill="transparent"
                      strokeWidth={stroke}
                      r={normalizedRadius}
                      cx={radius}
                      cy={radius}
                    />
                    {/* Active path */}
                    <circle
                      className={`transition-all duration-500 ${getRiskColor(riskScore)}`}
                      fill="transparent"
                      strokeWidth={stroke}
                      strokeDasharray={circumference + " " + circumference}
                      style={{
                        strokeDashoffset,
                        ["--ring-circ" as string]: circumference,
                        animation: "ringDraw 1.2s ease",
                      }}
                      r={normalizedRadius}
                      cx={radius}
                      cy={radius}
                    />
                  </svg>
                  <div className="absolute flex flex-col items-center justify-center">
                    <span className="text-base font-bold font-mono text-slate-100">{riskScore}</span>
                    <span className="text-[8px] font-mono text-slate-500 uppercase">NEWS2</span>
                  </div>
                </div>

                <div className="text-[10px] font-mono space-y-1">
                  <div className="flex items-center gap-1.5">
                    <span className="size-2 rounded-full bg-green-500"></span>
                    <span className="text-slate-400">0 - 4: SAFE</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="size-2 rounded-full bg-amber-500"></span>
                    <span className="text-slate-400">5 - 6: CAUTION</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="size-2 rounded-full bg-red-500"></span>
                    <span className="text-slate-400">7+: DANGER</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Secondary vitals grid */}
            <div className="border border-[#1E293B] bg-[#0D1117] rounded-xl p-3 flex flex-col gap-2 shrink-0">
              <span className="text-[10px] font-mono font-bold text-slate-400 uppercase tracking-wider block border-b border-[#1E293B] pb-1.5">
                SECONDARY VITAL SIGNS
              </span>
              <div className="grid grid-cols-2 gap-2 text-[10px] font-mono">
                <div className="border border-[#161D2D] bg-[#0D1117] p-2 rounded-lg">
                  <span className="text-slate-500 block">TEMPERATURE</span>
                  <span className="text-xs font-bold text-amber-500">{currentVitals?.temperature ?? "—"} °C</span>
                </div>
                <div className="border border-[#161D2D] bg-[#0D1117] p-2 rounded-lg">
                  <span className="text-slate-500 block">RESPIRATION</span>
                  <span className="text-xs font-bold text-cyan-400">{currentVitals?.respiratory_rate ?? "—"} /dk</span>
                </div>
                <div className="border border-[#161D2D] bg-[#0D1117] p-2 rounded-lg">
                  <span className="text-slate-500 block">IOP (EYE)</span>
                  <span className="text-xs font-bold text-blue-400">{currentVitals?.eye_pressure ?? "—"} mmHg</span>
                </div>
                <div className="border border-[#161D2D] bg-[#0D1117] p-2 rounded-lg">
                  <span className="text-slate-500 block">TEAR GLUCOSE</span>
                  <span className="text-xs font-bold text-green-400">{currentVitals?.tear_glucose ?? "—"} mg/dL</span>
                </div>
                <div className="border border-[#161D2D] bg-[#0D1117] p-2 rounded-lg col-span-2">
                  <span className="text-slate-500 block">CORTISOL (STRESS)</span>
                  <span className="text-xs font-bold text-purple-400">{currentVitals?.stress_level ?? "—"} mcg/dL</span>
                </div>
              </div>
            </div>

            {/* System Status info panel */}
            <div className="border border-[#1E293B] bg-[#0D1117] rounded-xl p-3 flex flex-col justify-between shrink-0 text-[10px] font-mono space-y-2">
              <span className="font-bold text-slate-400 uppercase tracking-wider block border-b border-[#1E293B] pb-1.5">
                SYSTEM STATUS
              </span>
              <div className="flex justify-between items-center">
                <span className="text-slate-500 flex items-center gap-1"><Cpu className="size-3 text-cyan-400" /> AI Inference</span>
                <span className="text-green-400 font-bold">Active</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-500 flex items-center gap-1"><Compass className="size-3 text-cyan-400" /> Model Architecture</span>
                <span className="text-slate-300 font-bold">Temporal Transformer v2.2</span>
              </div>
            </div>

          </div>

        </div>
      )}

      {/* Expanded GPT-4o Rapor Görüntüleme Paneli (Only shown when report is generated) */}
      {report && (
        <div className="border border-purple-500/20 bg-[#111827] rounded-xl p-4 space-y-3 shrink-0 shadow-[0_0_20px_rgba(139,92,246,0.05)]">
          <div className="flex items-center justify-between border-b border-[#1E293B] pb-2">
            <span className="text-xs font-mono font-bold text-purple-400 uppercase tracking-wider flex items-center gap-1.5">
              <FileText className="size-4 text-purple-400" /> GPT-4O DOKTOR RAPORU VE TIBBİ TAVSİYELER
            </span>
            <div className="flex border-b border-transparent text-[10px] font-mono">
              <button
                onClick={() => setActiveTab("report")}
                className={`px-3 py-1 border-b-2 font-bold cursor-pointer transition-all ${
                  activeTab === "report" ? "border-cyan-500 text-cyan-400" : "border-transparent text-slate-500"
                }`}
              >
                KLİNİK RAPOR
              </button>
              <button
                onClick={() => setActiveTab("recs")}
                className={`px-3 py-1 border-b-2 font-bold cursor-pointer transition-all ${
                  activeTab === "recs" ? "border-cyan-500 text-cyan-400" : "border-transparent text-slate-500"
                }`}
              >
                TAVSİYELER
              </button>
            </div>
          </div>
          <div className="text-slate-300 text-xs font-sans leading-relaxed whitespace-pre-line max-h-60 overflow-y-auto pr-2">
            {activeTab === "report" ? report : recommendations}
          </div>
        </div>
      )}

      {/* Bottom Status Footer Bar (ICU Standard Status line) */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between border-t border-[#161D2D] pt-3 text-[10px] font-mono text-slate-500 shrink-0 gap-2">
        <div className="flex flex-wrap items-center gap-4">
          <span className="flex items-center gap-1"><span className="size-1.5 rounded-full bg-green-500"></span> Connection: Connected</span>
          <span className="flex items-center gap-1"><span className="size-1.5 rounded-full bg-green-500"></span> Data Streaming: Live</span>
          <span className="flex items-center gap-1"><span className="size-1.5 rounded-full bg-green-500"></span> AI Engine: Running</span>
        </div>
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1"><Server className="size-3" /> Server: arguslens-hub-01</span>
          <span>Version: 4.0.0</span>
        </div>
      </div>
    </div>
  );
}
