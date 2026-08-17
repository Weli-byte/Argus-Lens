"use client";

import React from "react";
import { motion } from "framer-motion";
import { Thermometer, Zap } from "lucide-react";
import { cn } from "@/lib/utils";
import { clampPercent } from "@/lib/utils";

interface GPUBarProps {
  device_id: number;
  name: string;
  vram_used_mb: number;
  vram_total_mb: number;
  utilization_percent: number;
  temperature_celsius: number;
  className?: string;
}

const GPUBar = React.memo(function GPUBar({
  device_id,
  name,
  vram_used_mb,
  vram_total_mb,
  utilization_percent,
  temperature_celsius,
  className,
}: GPUBarProps) {
  const vramPct = clampPercent(vram_used_mb, vram_total_mb);
  const vramColor =
    vramPct > 80
      ? "bg-red-500"
      : vramPct > 60
        ? "bg-amber-500"
        : "bg-cyan-500";
  const tempHot = temperature_celsius > 80;

  return (
    <div
      className={cn(
        "rounded-xl border border-[rgba(0,212,255,0.1)] bg-[#0D1117] p-3 space-y-2 transition-colors duration-300 hover:border-[rgba(0,212,255,0.3)]",
        className
      )}
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-mono text-slate-400">GPU {device_id}</p>
          <p className="text-xs text-slate-500 truncate max-w-[140px]">{name}</p>
        </div>
        <div className="flex items-center gap-2">
          {tempHot && (
            <Thermometer className="size-3.5 text-red-400 animate-pulse" />
          )}
          <span
            className={cn(
              "text-xs font-mono",
              tempHot ? "text-red-400" : "text-slate-400"
            )}
          >
            {temperature_celsius}°C
          </span>
        </div>
      </div>

      {/* VRAM bar */}
      <div className="space-y-1">
        <div className="flex justify-between text-[10px] font-mono text-slate-500">
          <span>VRAM</span>
          <span>
            {Math.round(vram_used_mb)} / {Math.round(vram_total_mb)} MB
          </span>
        </div>
        <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${vramPct}%` }}
            transition={{ duration: 0.9, ease: "easeOut" }}
            className={cn("h-full rounded-full", vramColor)}
          />
        </div>
      </div>

      {/* Utilisation bar */}
      <div className="space-y-1">
        <div className="flex justify-between text-[10px] font-mono text-slate-500">
          <span className="flex items-center gap-1">
            <Zap className="size-2.5" />
            Util
          </span>
          <span>{Math.round(utilization_percent)}%</span>
        </div>
        <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${utilization_percent}%` }}
            transition={{ duration: 0.9, ease: "easeOut" }}
            className="h-full rounded-full bg-cyan-500 shadow-[0_0_8px_rgba(0,212,255,0.5)]"
          />
        </div>
      </div>
    </div>
  );
});

export default GPUBar;
