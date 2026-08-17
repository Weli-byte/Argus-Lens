"use client";

import React from "react";
import { cn } from "@/lib/utils";

type Status = "healthy" | "degraded" | "dead" | "unknown" | "recovering";

interface StatusBadgeProps {
  status: Status;
  label?: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}

const colours: Record<Status, { dot: string; text: string; bg: string }> = {
  healthy: {
    dot: "bg-cyan-400",
    text: "text-cyan-400",
    bg: "bg-cyan-500/10",
  },
  degraded: {
    dot: "bg-amber-500",
    text: "text-amber-400",
    bg: "bg-amber-500/10",
  },
  dead: { dot: "bg-red-500", text: "text-red-400", bg: "bg-red-500/10" },
  recovering: {
    dot: "bg-purple-400",
    text: "text-purple-300",
    bg: "bg-purple-500/10",
  },
  unknown: {
    dot: "bg-slate-500",
    text: "text-slate-400",
    bg: "bg-slate-500/10",
  },
};

const sizes = {
  sm: { dot: "size-1.5", text: "text-[10px]", pad: "px-1.5 py-0.5 gap-1" },
  md: { dot: "size-2", text: "text-xs", pad: "px-2 py-1 gap-1.5" },
  lg: { dot: "size-2.5", text: "text-sm", pad: "px-2.5 py-1 gap-2" },
};

const StatusBadge = React.memo(function StatusBadge({
  status,
  label,
  size = "md",
  className,
}: StatusBadgeProps) {
  const c = colours[status];
  const s = sizes[size];

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border border-transparent font-mono uppercase tracking-wider",
        c.bg,
        s.pad,
        className
      )}
    >
      <span
        className={cn(
          "rounded-full shrink-0",
          s.dot,
          c.dot,
          status === "healthy" && "animate-[pulse-slow_3s_ease-in-out_infinite]"
        )}
      />
      {label && <span className={cn(c.text, s.text)}>{label}</span>}
    </span>
  );
});

export default StatusBadge;
