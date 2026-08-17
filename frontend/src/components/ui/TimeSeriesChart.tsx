"use client";

import React, { useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ReferenceLine,
} from "recharts";
import { cn } from "@/lib/utils";
import type { TimeSeriesPoint } from "@/types";

interface TimeSeriesChartProps {
  data: TimeSeriesPoint[];
  dataKeys: string[];
  colors?: string[];
  title?: string;
  yDomain?: [number | "auto", number | "auto"];
  height?: number;
  showGrid?: boolean;
  referenceLines?: Array<{ x?: number; y?: number; label?: string; color?: string }>;
  className?: string;
  unit?: string;
}

const DEFAULT_COLORS = [
  "#00D4FF",
  "#7C3AED",
  "#10B981",
  "#F59E0B",
  "#EF4444",
  "#F97316",
];

const CustomTooltip = ({
  active,
  payload,
  label,
  unit,
}: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
  unit?: string;
}) => {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="rounded-xl border border-[rgba(0,212,255,0.25)] p-3 text-xs"
      style={{
        background: "rgba(13, 17, 23, 0.75)",
        backdropFilter: "blur(12px)",
        WebkitBackdropFilter: "blur(12px)",
        boxShadow: "0 12px 32px rgba(0,0,0,0.5), 0 0 20px rgba(0,212,255,0.08)",
      }}
    >
      <p className="text-slate-400 mb-1.5 font-mono">{label}</p>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center gap-2 py-0.5">
          <span
            className="size-1.5 rounded-full"
            style={{ background: p.color, boxShadow: `0 0 6px ${p.color}` }}
          />
          <span style={{ color: p.color }}>{p.name}</span>
          <span className="font-mono font-bold text-slate-100 ml-auto pl-4">
            {typeof p.value === "number" ? p.value.toFixed(2) : p.value}
            {unit ?? ""}
          </span>
        </div>
      ))}
    </div>
  );
};

const TimeSeriesChart = React.memo(function TimeSeriesChart({
  data,
  dataKeys,
  colors = DEFAULT_COLORS,
  title,
  yDomain = ["auto", "auto"],
  height = 200,
  showGrid = true,
  referenceLines = [],
  className,
  unit,
}: TimeSeriesChartProps) {
  const displayData = useMemo(() => data.slice(-120), [data]);

  return (
    <div className={cn("space-y-2", className)}>
      {title && (
        <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">
          {title}
        </p>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={displayData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
          {showGrid && (
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#1E293B"
              vertical={false}
            />
          )}
          <XAxis
            dataKey="time"
            tickFormatter={(v: number) =>
              new Date(v).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              })
            }
            tick={{ fill: "#475569", fontSize: 9 }}
            axisLine={false}
            tickLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={yDomain}
            tick={{ fill: "#475569", fontSize: 9 }}
            axisLine={false}
            tickLine={false}
            width={36}
          />
          <Tooltip content={<CustomTooltip unit={unit} />} />
          {dataKeys.length > 1 && (
            <Legend
              wrapperStyle={{ fontSize: 10, color: "#475569" }}
            />
          )}
          {referenceLines.map((rl, i) => (
            <ReferenceLine
              key={i}
              x={rl.x}
              y={rl.y}
              stroke={rl.color ?? "#475569"}
              strokeDasharray="4 2"
              label={{ value: rl.label, fill: "#475569", fontSize: 9 }}
            />
          ))}
          {dataKeys.map((key, i) => (
            <Line
              key={key}
              type="monotoneX"
              dataKey={key}
              stroke={colors[i % colors.length]}
              strokeWidth={1.5}
              dot={false}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
});

export default TimeSeriesChart;
