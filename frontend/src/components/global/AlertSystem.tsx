"use client";

import React, { useEffect, useCallback } from "react";
import { AnimatePresence } from "framer-motion";
import { useTemporalStore } from "@/store/temporal-store";
import AnomalyAlert from "@/components/ui/AnomalyAlert";

export default function AlertSystem() {
  const anomalies = useTemporalStore((s) => s.anomalies);
  const dismissAnomaly = useTemporalStore((s) => s.dismissAnomaly);

  // Play browser notification for CRITICAL anomalies if permitted
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<{ severity: string }>).detail;
      if (
        detail?.severity === "CRITICAL" &&
        "Notification" in window &&
        Notification.permission === "granted"
      ) {
        new Notification("ArgusLens — Critical Anomaly", {
          body: "A critical anomaly has been detected. Check the Temporal page.",
          icon: "/favicon.ico",
        });
      }
    };
    window.addEventListener("argus:anomaly", handler);
    return () => window.removeEventListener("argus:anomaly", handler);
  }, []);

  const handleDismiss = useCallback(
    (id: string) => dismissAnomaly(id),
    [dismissAnomaly]
  );

  const critical = anomalies.filter((a) => a.severity === "CRITICAL").slice(0, 3);

  if (critical.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 w-80 space-y-2 pointer-events-none">
      <AnimatePresence>
        {critical.map((a) => (
          <div key={a.id} className="pointer-events-auto">
            <AnomalyAlert anomaly={a} onDismiss={handleDismiss} />
          </div>
        ))}
      </AnimatePresence>
    </div>
  );
}
