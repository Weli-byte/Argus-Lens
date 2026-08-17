"use client";

import React, { useState } from "react";
import { Network, RefreshCw } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import WorkerNode from "@/components/ui/WorkerNode";
import StatusBadge from "@/components/ui/StatusBadge";
import MetricCard from "@/components/ui/MetricCard";
import { cn } from "@/lib/utils";

export default function WorkersPage() {
  const [refreshKey, setRefreshKey] = useState(0);

  const { data: clusterHealth, isPending, isError, refetch } = useQuery({
    queryKey: ["clusterHealth", refreshKey],
    queryFn: () => apiClient.getClusterHealth(),
    refetchInterval: 5_000,
    staleTime: 4_000,
  });

  const workers = clusterHealth?.workers ?? [];
  const healthyCount = workers.filter(
    (w) => w.state === "active" || w.state === "idle"
  ).length;
  const overloadedCount = workers.filter((w) => w.state === "overloaded").length;
  const deadCount = workers.filter((w) => w.state === "dead").length;

  const avgLoad =
    workers.length > 0
      ? workers.reduce((sum, w) => sum + w.current_load, 0) / workers.length
      : 0;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold font-mono text-slate-100 tracking-wider">
            WORKER NODES
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Distributed inference cluster management
          </p>
        </div>
        <div className="flex items-center gap-3">
          {clusterHealth && (
            <StatusBadge
              status={
                clusterHealth.cluster_status === "healthy"
                  ? "healthy"
                  : clusterHealth.cluster_status === "degraded"
                    ? "degraded"
                    : "dead"
              }
              label={clusterHealth.cluster_status}
              size="md"
            />
          )}
          <button
            onClick={() => {
              setRefreshKey((k) => k + 1);
              refetch();
            }}
            disabled={isPending}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-[#1E293B] text-slate-400 hover:text-slate-200 hover:border-[#2D4A6E] transition-colors text-xs font-mono"
          >
            <RefreshCw className={cn("size-3.5", isPending && "animate-spin")} />
            Refresh
          </button>
        </div>
      </div>

      {/* Cluster summary */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <MetricCard
          title="Total Workers"
          value={workers.length}
          icon={<Network className="size-4" />}
          color="cyan"
        />
        <MetricCard
          title="Healthy"
          value={healthyCount}
          unit={`/ ${workers.length}`}
          color="green"
          subtitle={`${workers.length > 0 ? Math.round((healthyCount / workers.length) * 100) : 0}%`}
        />
        <MetricCard
          title="Overloaded"
          value={overloadedCount}
          color={overloadedCount > 0 ? "amber" : "green"}
        />
        <MetricCard
          title="Avg Load"
          value={(avgLoad * 100).toFixed(1)}
          unit="%"
          color={avgLoad > 0.8 ? "red" : avgLoad > 0.6 ? "amber" : "cyan"}
        />
      </div>

      {isError && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 px-4 py-3 text-sm text-red-400 font-mono">
          Failed to load worker data. Retrying…
        </div>
      )}

      {/* Worker grid */}
      {workers.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {workers.map((worker) => (
            <WorkerNode key={worker.worker_id} worker={worker} />
          ))}
        </div>
      ) : (
        !isPending && (
          <div className="flex flex-col items-center justify-center rounded-xl border border-[#1E293B] bg-[#111827] py-20 gap-3">
            <Network className="size-12 text-slate-700" />
            <p className="text-sm text-slate-600">No workers connected</p>
          </div>
        )
      )}

      {isPending && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="h-24 rounded-lg border border-[#1E293B] bg-[#0D1117] animate-pulse"
            />
          ))}
        </div>
      )}

      {/* Dead workers section */}
      {deadCount > 0 && (
        <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4 space-y-3">
          <p className="text-xs font-medium text-red-400 uppercase tracking-wider">
            Dead Workers ({deadCount})
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {workers
              .filter((w) => w.state === "dead")
              .map((worker) => (
                <WorkerNode key={worker.worker_id} worker={worker} />
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
