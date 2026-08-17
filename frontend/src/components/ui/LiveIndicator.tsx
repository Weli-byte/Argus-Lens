"use client";

import React from "react";
import { cn } from "@/lib/utils";

interface LiveIndicatorProps {
  isLive: boolean;
  label?: string;
  className?: string;
}

const LiveIndicator = React.memo(function LiveIndicator({
  isLive,
  label = "LIVE",
  className,
}: LiveIndicatorProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-mono font-bold tracking-widest",
        isLive
          ? "text-cyan-400 bg-cyan-500/10 border border-cyan-500/30 shadow-[0_0_12px_rgba(0,212,255,0.15)]"
          : "text-slate-500 bg-slate-800 border border-slate-700",
        className
      )}
    >
      <span
        className={cn(
          "size-1.5 rounded-full",
          isLive
            ? "bg-cyan-400 animate-[pulse_1s_ease-in-out_infinite]"
            : "bg-slate-600"
        )}
      />
      {label}
    </span>
  );
});

export default LiveIndicator;
