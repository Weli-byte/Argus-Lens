"use client";

import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { AlertTriangle, AlertOctagon, Info, Zap, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AnomalyEvent } from "@/types";

interface AnomalyAlertProps {
  anomaly: AnomalyEvent;
  onDismiss?: (id: string) => void;
  className?: string;
}

const severityConfig = {
  LOW: {
    icon: Info,
    border: "border-blue-500/30",
    bg: "bg-blue-500/5",
    iconColor: "text-blue-400",
    textColor: "text-blue-300",
    badge: "bg-blue-500/20 text-blue-400",
    dot: "bg-blue-500",
  },
  MEDIUM: {
    icon: AlertTriangle,
    border: "border-amber-500/30",
    bg: "bg-amber-500/5",
    iconColor: "text-amber-400",
    textColor: "text-amber-300",
    badge: "bg-amber-500/20 text-amber-400",
    dot: "bg-amber-500",
  },
  HIGH: {
    icon: AlertTriangle,
    border: "border-orange-500/30",
    bg: "bg-orange-500/5",
    iconColor: "text-orange-400",
    textColor: "text-orange-300",
    badge: "bg-orange-500/20 text-orange-400",
    dot: "bg-orange-500",
  },
  CRITICAL: {
    icon: AlertOctagon,
    border: "border-red-500/30",
    bg: "bg-red-500/5",
    iconColor: "text-red-400",
    textColor: "text-red-300",
    badge: "bg-red-500/20 text-red-400",
    dot: "bg-red-500 animate-pulse",
  },
};

const AnomalyAlert = React.memo(function AnomalyAlert({
  anomaly,
  onDismiss,
  className,
}: AnomalyAlertProps) {
  const cfg = severityConfig[anomaly.severity];
  const Icon = cfg.icon;

  const ts = new Date(anomaly.timestamp).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, x: -12, height: 0 }}
        animate={{ opacity: 1, x: 0, height: "auto" }}
        exit={{ opacity: 0, x: 12, height: 0 }}
        transition={{ duration: 0.2, ease: "easeOut" }}
        className={cn(
          "rounded-lg border p-3 flex items-start gap-3 overflow-hidden",
          cfg.bg,
          cfg.border,
          className
        )}
      >
        <div className="shrink-0 mt-0.5">
          <Icon className={cn("size-4", cfg.iconColor)} />
        </div>

        <div className="flex-1 min-w-0 space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className={cn(
                "text-[10px] font-mono font-bold uppercase tracking-widest px-1.5 py-0.5 rounded",
                cfg.badge
              )}
            >
              {anomaly.severity}
            </span>
            <span className="text-[10px] font-mono text-slate-500">{ts}</span>
            {anomaly.model_id && (
              <span className="text-[10px] font-mono text-slate-600 truncate">
                {anomaly.model_id}
              </span>
            )}
          </div>

          <p className={cn("text-xs font-medium", cfg.textColor)}>
            {anomaly.type.replace(/_/g, " ")}
          </p>

          {anomaly.description && (
            <p className="text-[11px] text-slate-400 leading-relaxed line-clamp-2">
              {anomaly.description}
            </p>
          )}

          {anomaly.affected_metric && (
            <div className="flex items-center gap-1.5 mt-1">
              <Zap className="size-2.5 text-slate-500" />
              <span className="text-[10px] font-mono text-slate-500">
                {anomaly.affected_metric}
                {anomaly.metric_value !== undefined && (
                  <span className={cn("ml-1 font-bold", cfg.textColor)}>
                    {typeof anomaly.metric_value === "number"
                      ? anomaly.metric_value.toFixed(3)
                      : anomaly.metric_value}
                  </span>
                )}
              </span>
            </div>
          )}
        </div>

        {onDismiss && (
          <button
            onClick={() => onDismiss(anomaly.id)}
            className="shrink-0 text-slate-600 hover:text-slate-400 transition-colors p-0.5 rounded"
            aria-label="Dismiss alert"
          >
            <X className="size-3.5" />
          </button>
        )}
      </motion.div>
    </AnimatePresence>
  );
});

export default AnomalyAlert;
