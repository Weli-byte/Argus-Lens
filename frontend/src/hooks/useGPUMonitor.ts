"use client";

import { useQuery } from "@tanstack/react-query";
import { useSystemStore } from "@/store/system-store";
import api from "@/lib/api-client";

export function useGPUMonitor() {
  const setGPUMetrics = useSystemStore((s) => s.setGPUMetrics);
  const gpuMetrics = useSystemStore((s) => s.gpuMetrics);

  const { isPending, isError } = useQuery({
    queryKey: ["gpu-metrics"],
    queryFn: async () => {
      const data = await api.getGPUMetrics();
      setGPUMetrics(data);
      return data;
    },
    refetchInterval: 2_000,
    staleTime: 1_000,
    retry: 2,
  });

  return { gpuMetrics, isLoading: isPending, isError };
}
