"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Cpu, HardDrive, Wifi, WifiOff, ChevronDown, ChevronUp } from "lucide-react";
import { cn } from "@/lib/utils";
import StatusBadge from "./StatusBadge";
import type { WorkerInfo } from "@/types";

interface WorkerNodeProps {
  worker: WorkerInfo;
  className?: string;
}

const WorkerNode = React.memo(function WorkerNode({
  worker,
  className,
}: WorkerNodeProps) {
  const [expanded, setExpanded] = useState(false);

  const loadPct = Math.round(worker.current_load * 100);
  const loadColor =
    loadPct > 80 ? "bg-red-500" : loadPct > 60 ? "bg-amber-500" : "bg-cyan-500";

  const isOnline = worker.state === "active" || worker.state === "idle";

  return (
    <div
      className={cn(
        "rounded-lg border border-[#1E293B] bg-[#0D1117] overflow-hidden transition-colors duration-200",
        "hover:border-[#2D4A6E]",
        className
      )}
    >
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full p-3 flex items-center gap-3 text-left"
      >
        <div className="shrink-0">
          {isOnline ? (
            <Wifi className="size-4 text-cyan-400" />
          ) : (
            <WifiOff className="size-4 text-slate-600" />
          )}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-xs font-mono text-slate-200 truncate">
              {worker.worker_id}
            </p>
            <StatusBadge status={worker.state === "active" ? "healthy" : worker.state === "idle" ? "healthy" : worker.state === "overloaded" ? "degraded" : "dead"} size="sm" />
          </div>
          {worker.hostname && (
            <p className="text-[10px] text-slate-500 font-mono truncate mt-0.5">
              {worker.hostname}
            </p>
          )}
        </div>

        <div className="shrink-0 flex items-center gap-2">
          <span className="text-xs font-mono text-slate-400">{loadPct}%</span>
          {expanded ? (
            <ChevronUp className="size-3.5 text-slate-500" />
          ) : (
            <ChevronDown className="size-3.5 text-slate-500" />
          )}
        </div>
      </button>

      {/* Load bar */}
      <div className="px-3 pb-2">
        <div className="h-1 rounded-full bg-slate-800 overflow-hidden">
          <motion.div
            className={cn("h-full rounded-full", loadColor)}
            animate={{ width: `${loadPct}%` }}
            transition={{ duration: 0.5 }}
          />
        </div>
      </div>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="border-t border-[#1E293B] p-3 space-y-3">
              {/* Tasks */}
              <div className="flex items-center justify-between text-[11px] font-mono">
                <span className="text-slate-500">Active Tasks</span>
                <span className="text-slate-300">{worker.active_tasks ?? 0}</span>
              </div>
              <div className="flex items-center justify-between text-[11px] font-mono">
                <span className="text-slate-500">Queued Tasks</span>
                <span className="text-slate-300">{worker.queued_tasks ?? 0}</span>
              </div>
              <div className="flex items-center justify-between text-[11px] font-mono">
                <span className="text-slate-500">Completed</span>
                <span className="text-slate-300">{(worker.completed_tasks ?? 0).toLocaleString()}</span>
              </div>
              <div className="flex items-center justify-between text-[11px] font-mono">
                <span className="text-slate-500">Failed</span>
                <span className={(worker.failed_tasks ?? 0) > 0 ? "text-red-400" : "text-slate-300"}>
                  {worker.failed_tasks ?? 0}
                </span>
              </div>

              {/* Hardware */}
              {(worker.cpu_percent !== undefined || worker.memory_percent !== undefined) && (
                <div className="space-y-2 pt-1 border-t border-[#1E293B]">
                  {worker.cpu_percent !== undefined && (
                    <div className="space-y-1">
                      <div className="flex items-center justify-between text-[10px] font-mono text-slate-500">
                        <span className="flex items-center gap-1">
                          <Cpu className="size-2.5" />
                          CPU
                        </span>
                        <span>{Math.round(worker.cpu_percent)}%</span>
                      </div>
                      <div className="h-1 rounded-full bg-slate-800 overflow-hidden">
                        <div
                          className="h-full rounded-full bg-purple-500 transition-all duration-500"
                          style={{ width: `${worker.cpu_percent}%` }}
                        />
                      </div>
                    </div>
                  )}
                  {worker.memory_percent !== undefined && (
                    <div className="space-y-1">
                      <div className="flex items-center justify-between text-[10px] font-mono text-slate-500">
                        <span className="flex items-center gap-1">
                          <HardDrive className="size-2.5" />
                          Memory
                        </span>
                        <span>{Math.round(worker.memory_percent)}%</span>
                      </div>
                      <div className="h-1 rounded-full bg-slate-800 overflow-hidden">
                        <div
                          className="h-full rounded-full bg-green-500 transition-all duration-500"
                          style={{ width: `${worker.memory_percent}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Capabilities */}
              {(worker.capabilities?.length ?? 0) > 0 && (
                <div className="flex flex-wrap gap-1 pt-1 border-t border-[#1E293B]">
                  {(worker.capabilities ?? []).map((cap) => (
                    <span
                      key={cap}
                      className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 uppercase tracking-wider"
                    >
                      {cap}
                    </span>
                  ))}
                </div>
              )}

              {/* Last heartbeat */}
              {worker.last_heartbeat && (
                <p className="text-[10px] font-mono text-slate-600">
                  Last seen: {new Date(worker.last_heartbeat).toLocaleTimeString()}
                </p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
});

export default WorkerNode;
