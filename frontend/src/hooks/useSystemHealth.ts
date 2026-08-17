"use client";

import { useQuery } from "@tanstack/react-query";
import { useSystemStore } from "@/store/system-store";
import api from "@/lib/api-client";

export function useSystemHealth() {
  const setSystemHealth = useSystemStore((s) => s.setSystemHealth);
  const systemHealth = useSystemStore((s) => s.systemHealth);

  const { isPending, isError } = useQuery({
    queryKey: ["system-health"],
    queryFn: async () => {
      const data = await api.getSystemHealth();
      setSystemHealth(data);
      return data;
    },
    refetchInterval: 5_000,
    staleTime: 5_000,
    retry: 2,
  });

  const isHealthy = systemHealth ? systemHealth.score >= 70 : null;
  const criticalIssues = systemHealth?.issues ?? [];

  return { health: systemHealth, isHealthy, criticalIssues, isLoading: isPending, isError };
}
