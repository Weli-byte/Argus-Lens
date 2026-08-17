"use client";

import React from "react";
import { motion } from "framer-motion";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { cn } from "@/lib/utils";
import CountUp from "@/components/ui/CountUp";
import TiltCard from "@/components/ui/TiltCard";

interface MetricCardProps {
  title: string;
  value: string | number;
  unit?: string;
  trend?: number;
  trendDirection?: "up" | "down" | "neutral";
  icon?: React.ReactNode;
  color?: "cyan" | "green" | "amber" | "red" | "purple";
  className?: string;
  subtitle?: string;
  delay?: number;
}

const valueColorMap = {
  cyan: "text-cyan-400",
  green: "text-green-400",
  amber: "text-amber-400",
  red: "text-red-400",
  purple: "text-purple-400",
};

const badgeColorMap = {
  cyan: "bg-cyan-500/10 text-cyan-400 border-cyan-500/20",
  green: "bg-green-500/10 text-green-400 border-green-500/20",
  amber: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  red: "bg-red-500/10 text-red-400 border-red-500/20",
  purple: "bg-purple-500/10 text-purple-400 border-purple-500/20",
};

const MetricCard = React.memo(function MetricCard({
  title,
  value,
  unit,
  trend,
  trendDirection = "neutral",
  icon,
  color = "cyan",
  className,
  subtitle,
  delay = 0,
}: MetricCardProps) {
  const trendIcon =
    trendDirection === "up" ? (
      <TrendingUp className="size-3" />
    ) : trendDirection === "down" ? (
      <TrendingDown className="size-3" />
    ) : (
      <Minus className="size-3" />
    );

  const trendColor =
    trendDirection === "up"
      ? "text-green-400"
      : trendDirection === "down"
        ? "text-red-400"
        : "text-slate-500";

  return (
    <TiltCard className="h-full">
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, delay, ease: "easeOut" }}
      className={cn(
        "card-lift h-full rounded-2xl border border-[rgba(0,212,255,0.15)] bg-gradient-to-br from-[#0D1117] to-[#111827] p-6 flex flex-col gap-4",
        className
      )}
    >
      <div className="flex items-start justify-between">
        <span className="text-xs text-slate-400 font-semibold uppercase tracking-widest">
          {title}
        </span>
        {icon && (
          <span className="text-cyan-400 opacity-70 [&>svg]:size-6">
            {icon}
          </span>
        )}
      </div>

      <div className="flex items-end gap-2">
        <span
          className={cn(
            "text-4xl font-extrabold tracking-tight tabular-nums",
            valueColorMap[color]
          )}
        >
          {Number.isFinite(Number(value)) && String(value).trim() !== "" ? (
            <CountUp
              value={Number(value)}
              decimals={String(value).includes(".") ? String(value).split(".")[1].length : 0}
            />
          ) : (
            value
          )}
        </span>
        {unit && (
          <span className="text-sm text-slate-500 mb-1 font-mono">{unit}</span>
        )}
      </div>

      <div className="flex items-center justify-between">
        {subtitle && (
          <span
            className={cn(
              "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border text-[10px] font-semibold uppercase tracking-wider",
              badgeColorMap[color]
            )}
          >
            <span className="size-1.5 rounded-full bg-current" />
            {subtitle}
          </span>
        )}
        {trend !== undefined && (
          <span className={cn("flex items-center gap-1 text-xs font-mono", trendColor)}>
            {trendIcon}
            {Math.abs(trend).toFixed(1)}%
          </span>
        )}
      </div>
    </motion.div>
    </TiltCard>
  );
});

export default MetricCard;
