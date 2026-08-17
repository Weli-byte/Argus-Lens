"use client";

import React from "react";
import { motion } from "framer-motion";
import { Wifi, WifiOff, RefreshCw, Radio } from "lucide-react";
import { cn } from "@/lib/utils";
import { useWSStore } from "@/store/ws-store";
import { getWSClient } from "@/lib/ws-client";
import type { WSConnectionState } from "@/types";

interface ConnectionHealthProps {
  className?: string;
}

const stateConfig: Record<
  WSConnectionState,
  { label: string; color: string; icon: typeof Wifi; animate?: boolean }
> = {
  connecting: {
    label: "Connecting",
    color: "text-amber-400",
    icon: Radio,
    animate: true,
  },
  connected: {
    label: "Live",
    color: "text-cyan-400",
    icon: Wifi,
  },
  reconnecting: {
    label: "Reconnecting",
    color: "text-amber-400",
    icon: RefreshCw,
    animate: true,
  },
  disconnected: {
    label: "Disconnected",
    color: "text-slate-500",
    icon: WifiOff,
  },
  error: {
    label: "Error",
    color: "text-red-400",
    icon: WifiOff,
  },
};

const ConnectionHealth = React.memo(function ConnectionHealth({
  className,
}: ConnectionHealthProps) {
  const { connectionState, latency, reconnectAttempts } = useWSStore();
  const cfg = stateConfig[connectionState];
  const Icon = cfg.icon;

  const handleReconnect = () => {
    try {
      const client = getWSClient();
      const token = (window as unknown as { __argus_token?: string }).__argus_token;
      if (token) {
        client.connect(window.location.origin, token);
      } else {
        window.location.replace("/login");
      }
    } catch {
      // ignore
    }
  };

  const latencyColor =
    latency === null
      ? "text-slate-500"
      : latency < 50
        ? "text-cyan-400"
        : latency < 150
          ? "text-amber-400"
          : "text-red-400";

  return (
    <div
      className={cn(
        "flex items-center gap-3 rounded-full border border-[rgba(0,212,255,0.15)] bg-[#0D1117]/80 px-3.5 py-2",
        className
      )}
    >
      <motion.div
        animate={cfg.animate ? { opacity: [1, 0.3, 1] } : { opacity: 1 }}
        transition={cfg.animate ? { repeat: Infinity, duration: 1.2 } : {}}
      >
        <Icon className={cn("size-4", cfg.color)} />
      </motion.div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={cn("text-xs font-mono font-medium", cfg.color)}>
            {cfg.label}
          </span>
          {connectionState === "reconnecting" && reconnectAttempts > 0 && (
            <span className="text-[10px] font-mono text-slate-500">
              #{reconnectAttempts}
            </span>
          )}
        </div>
        {latency !== null && connectionState === "connected" && (
          <span className={cn("text-[10px] font-mono", latencyColor)}>
            {latency}ms RTT
          </span>
        )}
      </div>

      {(connectionState === "disconnected" || connectionState === "error") && (
        <button
          onClick={handleReconnect}
          className="shrink-0 flex items-center gap-1 text-[10px] font-mono text-cyan-500 hover:text-cyan-300 transition-colors px-2 py-1 rounded border border-cyan-500/30 hover:border-cyan-400/50"
        >
          <RefreshCw className="size-2.5" />
          Reconnect
        </button>
      )}
    </div>
  );
});

export default ConnectionHealth;
