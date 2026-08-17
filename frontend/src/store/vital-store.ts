import { create } from "zustand";
import { produce } from "immer";
import type { VitalTelemetry } from "@/types";

const MAX_HISTORY = 300;

interface VitalState {
  currentTelemetry: VitalTelemetry | null;
  history: VitalTelemetry[];
  report: string | null;
  recommendations: string | null;
  generatingReport: boolean;
  reportError: string | null;
}

interface VitalActions {
  addRecord: (record: VitalTelemetry) => void;
  setHistory: (history: VitalTelemetry[]) => void;
  setReportData: (report: string, recommendations: string) => void;
  setGeneratingReport: (val: boolean) => void;
  setReportError: (err: string | null) => void;
  reset: () => void;
}

const initial: VitalState = {
  currentTelemetry: null,
  history: [],
  report: null,
  recommendations: null,
  generatingReport: false,
  reportError: null,
};

export const useVitalStore = create<VitalState & VitalActions>((set) => ({
  ...initial,

  addRecord: (record) =>
    set(
      produce((state: VitalState) => {
        state.currentTelemetry = record;
        state.history.push(record);
        if (state.history.length > MAX_HISTORY) {
          state.history.shift();
        }
      })
    ),

  setHistory: (history) => set({ history }),
  
  setReportData: (report, recommendations) =>
    set({ report, recommendations, generatingReport: false, reportError: null }),

  setGeneratingReport: (val) => set({ generatingReport: val }),

  setReportError: (err) => set({ reportError: err, generatingReport: false }),

  reset: () => set(initial),
}));
