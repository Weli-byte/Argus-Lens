"use client";

import { useEffect } from "react";
import { getWSClient } from "@/lib/ws-client";
import { useTemporalStore } from "@/store/temporal-store";
import type { TemporalMetrics, AnomalyEvent, TemporalForecast } from "@/types";

export function useTemporalStream() {
  const setMetrics = useTemporalStore((s) => s.setMetrics);
  const addAnomaly = useTemporalStore((s) => s.addAnomaly);
  const setForecast = useTemporalStore((s) => s.setForecast);
  const setRiskLevel = useTemporalStore((s) => s.setRiskLevel);

  const currentMetrics = useTemporalStore((s) => s.currentMetrics);
  const anomalies = useTemporalStore((s) => s.anomalies);
  const forecast = useTemporalStore((s) => s.forecast);
  const riskLevel = useTemporalStore((s) => s.riskLevel);

  useEffect(() => {
    const client = getWSClient();

    const unsubMetrics = client.on<TemporalMetrics>("temporal_metrics", (m) => {
      setMetrics(m);

      // Auto-derive risk from fatigue + focus
      const fatigue = m.fatigue_score;
      const focus = m.focus_score;
      if (fatigue > 0.85 || focus < 0.1) setRiskLevel("DANGER");
      else if (fatigue > 0.65 || focus < 0.25) setRiskLevel("WARNING");
      else if (fatigue > 0.45 || focus < 0.45) setRiskLevel("CAUTION");
      else setRiskLevel("SAFE");
    });

    const unsubAnomaly = client.on<AnomalyEvent>("anomaly_detected", (a) => {
      addAnomaly(a);
      // Dispatch global alert for critical anomalies
      if (a.severity === "CRITICAL" || a.severity === "HIGH") {
        window.dispatchEvent(new CustomEvent("argus:anomaly", { detail: a }));
      }
    });

    const unsubForecast = client.on<TemporalForecast>(
      "temporal_forecast",
      (f) => {
        setForecast(f);
        setRiskLevel(f.risk_level);
      }
    );

    return () => {
      unsubMetrics();
      unsubAnomaly();
      unsubForecast();
    };
  }, [setMetrics, addAnomaly, setForecast, setRiskLevel]);

  return { currentMetrics, anomalies, forecast, riskLevel };
}
