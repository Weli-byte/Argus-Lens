import { create } from "zustand";
import type { SystemHealth, GPUMetrics, ClusterHealth, ModelVersion } from "@/types";

interface SystemState {
  systemHealth: SystemHealth | null;
  gpuMetrics: GPUMetrics | null;
  clusterHealth: ClusterHealth | null;
  models: ModelVersion[];
}

interface SystemActions {
  setSystemHealth: (h: SystemHealth) => void;
  setGPUMetrics: (m: GPUMetrics) => void;
  setClusterHealth: (c: ClusterHealth) => void;
  setModels: (m: ModelVersion[]) => void;
}

export const useSystemStore = create<SystemState & SystemActions>((set) => ({
  systemHealth: null,
  gpuMetrics: null,
  clusterHealth: null,
  models: [],
  setSystemHealth: (h) => set({ systemHealth: h }),
  setGPUMetrics: (m) => set({ gpuMetrics: m }),
  setClusterHealth: (c) => set({ clusterHealth: c }),
  setModels: (m) => set({ models: m }),
}));
