"use client";

import React, { useMemo } from "react";
import { Brain, Activity, TrendingUp, AlertTriangle } from "lucide-react";
import { useTemporalStore } from "@/store/temporal-store";
import { useTemporalStream } from "@/hooks/useTemporalStream";
import TimeSeriesChart from "@/components/ui/TimeSeriesChart";
import AnomalyAlert from "@/components/ui/AnomalyAlert";
import MetricCard from "@/components/ui/MetricCard";
import { cn } from "@/lib/utils";
import type { TimeSeriesPoint } from "@/types";

const RISK_STYLES = {
  SAFE: { border: "border-green-500/30", bg: "bg-green-500/5", text: "text-green-400", label: "SAFE" },
  CAUTION: { border: "border-amber-500/30", bg: "bg-amber-500/5", text: "text-amber-400", label: "CAUTION" },
  WARNING: { border: "border-orange-500/30", bg: "bg-orange-500/5", text: "text-orange-400", label: "WARNING" },
  DANGER: { border: "border-red-500/30", bg: "bg-red-500/5", text: "text-red-400", label: "DANGER" },
} as const;

export default function TemporalPage() {
  useTemporalStream();

  const { currentMetrics, metricsHistory, anomalies, forecast, riskLevel } =
    useTemporalStore();

  const chartData = useMemo<TimeSeriesPoint[]>(
    () =>
      metricsHistory.slice(-120).map((m) => ({
        time: new Date(m.timestamp).getTime(),
        fatigue: m.fatigue_score * 100,
        focus: m.focus_score * 100,
        cognitive_load: m.cognitive_load * 100,
      })),
    [metricsHistory]
  );

  const anomalyTimelineData = useMemo<TimeSeriesPoint[]>(
    () =>
      anomalies.slice(0, 50).map((a) => ({
        time: new Date(a.timestamp).getTime(),
        severity:
          a.severity === "CRITICAL"
            ? 4
            : a.severity === "HIGH"
              ? 3
              : a.severity === "MEDIUM"
                ? 2
                : 1,
      })),
    [anomalies]
  );

  const riskCfg = RISK_STYLES[riskLevel];

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold font-mono text-slate-100 tracking-wider">
            TEMPORAL ANALYTICS
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Cognitive load, fatigue, and behavioral drift analysis
          </p>
        </div>
      </div>

      {/* Risk banner */}
      <div
        className={cn(
          "rounded-xl border px-5 py-3 flex items-center justify-between",
          riskCfg.border,
          riskCfg.bg
        )}
      >
        <div className="flex items-center gap-3">
          <AlertTriangle className={cn("size-5", riskCfg.text)} />
          <div>
            <span className={cn("text-sm font-bold font-mono", riskCfg.text)}>
              Risk Level: {riskCfg.label}
            </span>
            {forecast && (
              <p className="text-xs text-slate-400 mt-0.5">
                Forecast: {forecast.predicted_events} events in next{" "}
                {forecast.time_horizon_minutes}m
              </p>
            )}
          </div>
        </div>
        {forecast && (
          <div className="text-right">
            <p className={cn("text-sm font-mono font-bold", riskCfg.text)}>
              {(forecast.confidence * 100).toFixed(0)}%
            </p>
            <p className="text-[10px] text-slate-500 font-mono">confidence</p>
          </div>
        )}
      </div>

      {/* Current metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <MetricCard
          title="Fatigue Score"
          value={
            currentMetrics
              ? (currentMetrics.fatigue_score * 100).toFixed(1)
              : "—"
          }
          unit="%"
          icon={<Brain className="size-4" />}
          color={
            currentMetrics && currentMetrics.fatigue_score > 0.7
              ? "red"
              : currentMetrics && currentMetrics.fatigue_score > 0.5
                ? "amber"
                : "green"
          }
        />
        <MetricCard
          title="Focus Score"
          value={
            currentMetrics
              ? (currentMetrics.focus_score * 100).toFixed(1)
              : "—"
          }
          unit="%"
          icon={<Activity className="size-4" />}
          color={
            currentMetrics && currentMetrics.focus_score < 0.3
              ? "red"
              : currentMetrics && currentMetrics.focus_score < 0.6
                ? "amber"
                : "cyan"
          }
        />
        <MetricCard
          title="Cognitive Load"
          value={
            currentMetrics
              ? (currentMetrics.cognitive_load * 100).toFixed(1)
              : "—"
          }
          unit="%"
          icon={<TrendingUp className="size-4" />}
          color={
            currentMetrics && currentMetrics.cognitive_load > 0.8
              ? "red"
              : "purple"
          }
        />
        <MetricCard
          title="Anomalies (24h)"
          value={anomalies.length}
          icon={<AlertTriangle className="size-4" />}
          color={anomalies.length > 10 ? "red" : anomalies.length > 5 ? "amber" : "green"}
          subtitle={
            anomalies.filter((a) => a.severity === "CRITICAL").length +
            " critical"
          }
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="rounded-xl border border-[#1E293B] bg-[#111827] p-4">
          <TimeSeriesChart
            data={chartData}
            dataKeys={["fatigue", "focus", "cognitive_load"]}
            colors={["#EF4444", "#00D4FF", "#7C3AED"]}
            title="Cognitive Metrics Over Time"
            yDomain={[0, 100]}
            height={200}
            unit="%"
          />
        </div>
        <div className="rounded-xl border border-[#1E293B] bg-[#111827] p-4">
          <TimeSeriesChart
            data={anomalyTimelineData}
            dataKeys={["severity"]}
            colors={["#EF4444"]}
            title="Anomaly Timeline (10 min)"
            yDomain={[0, 4]}
            height={200}
            referenceLines={[
              { y: 3, label: "HIGH", color: "#F97316" },
              { y: 4, label: "CRITICAL", color: "#EF4444" },
            ]}
          />
        </div>
      </div>

      {/* Anomaly list + forecast */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 rounded-xl border border-[#1E293B] bg-[#111827] p-4 space-y-2">
          <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">
            Anomaly Feed
          </p>
          {anomalies.length > 0 ? (
            <div className="space-y-2 max-h-72 overflow-y-auto">
              {anomalies.map((a) => (
                <AnomalyAlert key={a.id} anomaly={a} />
              ))}
            </div>
          ) : (
            <div className="flex items-center justify-center py-10">
              <p className="text-xs text-slate-600">No anomalies detected</p>
            </div>
          )}
        </div>

        {/* Forecast panel */}
        {forecast && (
          <div className="rounded-xl border border-[#1E293B] bg-[#111827] p-4 space-y-4">
            <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">
              Forecast
            </p>
            <div className="space-y-3">
              <div className="flex justify-between text-xs font-mono">
                <span className="text-slate-500">Risk Level</span>
                <span className={cn("font-bold", RISK_STYLES[forecast.risk_level].text)}>
                  {forecast.risk_level}
                </span>
              </div>
              <div className="flex justify-between text-xs font-mono">
                <span className="text-slate-500">Predicted Events</span>
                <span className="text-slate-300">{forecast.predicted_events}</span>
              </div>
              <div className="flex justify-between text-xs font-mono">
                <span className="text-slate-500">Time Horizon</span>
                <span className="text-slate-300">{forecast.time_horizon_minutes}m</span>
              </div>
              <div className="flex justify-between text-xs font-mono">
                <span className="text-slate-500">Confidence</span>
                <span className="text-slate-300">
                  {(forecast.confidence * 100).toFixed(0)}%
                </span>
              </div>
              {forecast.recommendations && forecast.recommendations.length > 0 && (
                <div className="pt-2 border-t border-[#1E293B] space-y-1.5">
                  <p className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">
                    Recommendations
                  </p>
                  {forecast.recommendations.map((r, i) => (
                    <p key={i} className="text-[11px] text-slate-400 leading-relaxed">
                      • {r}
                    </p>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
