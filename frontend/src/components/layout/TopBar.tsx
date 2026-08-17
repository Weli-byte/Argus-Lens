"use client";

import React, { useEffect, useState, useMemo } from "react";
import { Bell, User, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/store/auth-store";
import { useTemporalStore } from "@/store/temporal-store";
import LiveIndicator from "@/components/ui/LiveIndicator";
import ConnectionHealth from "@/components/ui/ConnectionHealth";
import { useWSStore } from "@/store/ws-store";

export default function TopBar() {
  const [clock, setClock] = useState("");
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const anomalies = useTemporalStore((s) => s.anomalies);
  const connectionState = useWSStore((s) => s.connectionState);

  const alertCount = useMemo(
    () => anomalies.filter((a) => a.severity === "HIGH" || a.severity === "CRITICAL").length,
    [anomalies]
  );

  // Tick clock every second
  useEffect(() => {
    const update = () => {
      setClock(
        new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: false,
        })
      );
    };
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <header className="flex items-center gap-4 px-5 py-2.5 bg-[#080B0F] border-b border-[rgba(255,255,255,0.06)] min-h-[57px] shrink-0">
      {/* Clock */}
      <div className="font-mono text-xs text-slate-300 tabular-nums tracking-wider min-w-[80px]">
        {clock}
      </div>

      {/* Connection indicator */}
      <ConnectionHealth className="py-1.5" />

      <div className="flex-1" />

      {/* Live indicator */}
      <LiveIndicator
        isLive={connectionState === "connected"}
        label="CANLI"
        className="rounded-full px-3"
      />

      {/* Alert bell */}
      <button className="relative p-1.5 rounded-lg hover:bg-slate-800 transition-colors">
        <Bell
          className={cn(
            "size-4",
            alertCount > 0 ? "text-red-400" : "text-slate-500"
          )}
        />
        {alertCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 size-4 rounded-full bg-red-500 text-[9px] font-bold text-white flex items-center justify-center">
            {alertCount > 9 ? "9+" : alertCount}
          </span>
        )}
      </button>

      {/* User menu */}
      <div className="relative">
        <button
          onClick={() => setUserMenuOpen((v) => !v)}
          className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-slate-800 transition-colors"
        >
          <div className="size-7 rounded-full bg-cyan-500/15 border-2 border-cyan-500/50 flex items-center justify-center">
            <User className="size-3.5 text-cyan-400" />
          </div>
          <span className="text-xs font-semibold text-slate-200">
            {user?.username ?? "operator"}
          </span>
          <ChevronDown className="size-3 text-slate-500" />
        </button>

        {userMenuOpen && (
          <>
            <div
              className="fixed inset-0 z-10"
              onClick={() => setUserMenuOpen(false)}
            />
            <div className="absolute right-0 top-full mt-1 z-20 w-48 rounded-lg border border-[#1E293B] bg-[#0D1117] shadow-xl overflow-hidden">
              <div className="px-3 py-2 border-b border-[#1E293B]">
                <p className="text-xs font-mono text-slate-300">
                  {user?.username ?? "operator"}
                </p>
                <p className="text-[10px] text-slate-500">{user?.role ?? "operator"}</p>
              </div>
              <button
                onClick={() => {
                  setUserMenuOpen(false);
                  logout();
                }}
                className="w-full px-3 py-2 text-left text-xs text-red-400 hover:bg-red-500/5 transition-colors"
              >
                Sign Out
              </button>
            </div>
          </>
        )}
      </div>
    </header>
  );
}
