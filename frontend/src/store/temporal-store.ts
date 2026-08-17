import { create } from "zustand";
import { produce } from "immer";
import type { TemporalMetrics, AnomalyEvent, TemporalForecast } from "@/types";

type RiskLevel = "SAFE" | "CAUTION" | "WARNING" | "DANGER";

const MAX_HISTORY = 500;
const MAX_ANOMALIES = 50;

interface TemporalState {
  currentMetrics: TemporalMetrics | null;
  metricsHistory: TemporalMetrics[];
  anomalies: AnomalyEvent[];
  forecast: TemporalForecast | null;
  riskLevel: RiskLevel;
}

interface TemporalActions {
  setMetrics: (m: TemporalMetrics) => void;
  addAnomaly: (a: AnomalyEvent) => void;
  dismissAnomaly: (id: string) => void;
  setForecast: (f: TemporalForecast) => void;
  setRiskLevel: (r: RiskLevel) => void;
  reset: () => void;
}

const initial: TemporalState = {
  currentMetrics: null,
  metricsHistory: [],
  anomalies: [],
  forecast: null,
  riskLevel: "SAFE",
};

export const useTemporalStore = create<TemporalState & TemporalActions>(
  (set) => ({
    ...initial,

    setMetrics: (m) =>
      set(
        produce((state: TemporalState) => {
          state.currentMetrics = m;
          state.metricsHistory.push(m);
          if (state.metricsHistory.length > MAX_HISTORY) {
            state.metricsHistory.shift();
          }
        })
      ),

    addAnomaly: (a) =>
      set(
        produce((state: TemporalState) => {
          state.anomalies.unshift(a);
          if (state.anomalies.length > MAX_ANOMALIES) {
            state.anomalies.pop();
          }
        })
      ),

    dismissAnomaly: (id) =>
      set(
        produce((state: TemporalState) => {
          state.anomalies = state.anomalies.filter((a) => a.id !== id);
        })
      ),

    setForecast: (f) => set({ forecast: f }),
    setRiskLevel: (r) => set({ riskLevel: r }),
    reset: () => set(initial),
  })
);
