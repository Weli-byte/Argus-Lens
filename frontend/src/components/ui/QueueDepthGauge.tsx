"use client";

import React, { useMemo } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface QueueDepthGaugeProps {
  current: number;
  max: number;
  label?: string;
  unit?: string;
  warnAt?: number;
  critAt?: number;
  size?: number;
  className?: string;
}

const QueueDepthGauge = React.memo(function QueueDepthGauge({
  current,
  max,
  label = "Queue Depth",
  unit = "jobs",
  warnAt = 0.6,
  critAt = 0.85,
  size = 120,
  className,
}: QueueDepthGaugeProps) {
  const pct = Math.min(current / Math.max(max, 1), 1);

  const { color, trackColor, textColor } = useMemo(() => {
    if (pct >= critAt)
      return {
        color: "#EF4444",
        trackColor: "rgba(239,68,68,0.15)",
        textColor: "text-red-400",
      };
    if (pct >= warnAt)
      return {
        color: "#F59E0B",
        trackColor: "rgba(245,158,11,0.15)",
        textColor: "text-amber-400",
      };
    return {
      color: "#00D4FF",
      trackColor: "rgba(0,212,255,0.12)",
      textColor: "text-cyan-400",
    };
  }, [pct, warnAt, critAt]);

  const radius = (size - 20) / 2;
  const circumference = 2 * Math.PI * radius;
  const strokeLen = circumference * 0.75;
  const gap = circumference * 0.25;
  const offset = circumference * 0.125 + gap / 2;
  const filledLen = strokeLen * pct;

  const center = size / 2;

  return (
    <div className={cn("flex flex-col items-center gap-2", className)}>
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          className="-rotate-[225deg]"
        >
          {/* Track */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke={trackColor}
            strokeWidth={8}
            strokeDasharray={`${strokeLen} ${gap}`}
            strokeDashoffset={-offset}
            strokeLinecap="round"
          />
          {/* Fill */}
          <motion.circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={8}
            strokeDasharray={`${filledLen} ${circumference - filledLen}`}
            strokeDashoffset={-offset}
            strokeLinecap="round"
            initial={{ strokeDasharray: `0 ${circumference}` }}
            animate={{
              strokeDasharray: `${filledLen} ${circumference - filledLen}`,
            }}
            transition={{ duration: 1.2, ease: "easeOut" }}
          />
        </svg>

        {/* Center text */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <motion.span
            key={current}
            initial={{ opacity: 0.5 }}
            animate={{ opacity: 1 }}
            className={cn("text-xl font-bold font-mono", textColor)}
          >
            {current}
          </motion.span>
          <span className="text-[9px] font-mono text-slate-500 uppercase tracking-wider">
            / {max}
          </span>
        </div>
      </div>

      <div className="text-center space-y-0.5">
        <p className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">
          {label}
        </p>
        <p className={cn("text-[10px] font-mono", textColor)}>
          {Math.round(pct * 100)}% • {unit}
        </p>
      </div>
    </div>
  );
});

export default QueueDepthGauge;
