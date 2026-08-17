"use client";

import React, { useEffect, useState, useCallback } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X, CheckCircle, AlertTriangle, Info, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

type NotificationLevel = "info" | "success" | "warning" | "error";

interface Notification {
  id: string;
  level: NotificationLevel;
  message: string;
  ttl?: number;
}

const LEVEL_STYLES: Record<NotificationLevel, { icon: typeof Info; border: string; bg: string; text: string }> = {
  info: { icon: Info, border: "border-blue-500/30", bg: "bg-blue-500/5", text: "text-blue-300" },
  success: { icon: CheckCircle, border: "border-green-500/30", bg: "bg-green-500/5", text: "text-green-300" },
  warning: { icon: AlertTriangle, border: "border-amber-500/30", bg: "bg-amber-500/5", text: "text-amber-300" },
  error: { icon: XCircle, border: "border-red-500/30", bg: "bg-red-500/5", text: "text-red-300" },
};

declare global {
  interface WindowEventMap {
    "argus:notify": CustomEvent<Omit<Notification, "id">>;
    "argus:circuit-open": CustomEvent<{ endpoint: string }>;
  }
}

export default function SystemNotification() {
  const [notifications, setNotifications] = useState<Notification[]>([]);

  const addNotification = useCallback((n: Omit<Notification, "id">) => {
    const id = crypto.randomUUID();
    setNotifications((prev) => [...prev.slice(-4), { ...n, id }]);
    const ttl = n.ttl ?? 5000;
    setTimeout(
      () => setNotifications((prev) => prev.filter((x) => x.id !== id)),
      ttl
    );
  }, []);

  useEffect(() => {
    const handleNotify = (e: CustomEvent<Omit<Notification, "id">>) => {
      addNotification(e.detail);
    };
    const handleCircuitOpen = (e: CustomEvent<{ endpoint: string }>) => {
      addNotification({
        level: "error",
        message: `Circuit breaker open: ${e.detail.endpoint}`,
        ttl: 8000,
      });
    };

    window.addEventListener("argus:notify", handleNotify);
    window.addEventListener("argus:circuit-open", handleCircuitOpen);
    return () => {
      window.removeEventListener("argus:notify", handleNotify);
      window.removeEventListener("argus:circuit-open", handleCircuitOpen);
    };
  }, [addNotification]);

  const dismiss = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  return (
    <div className="fixed top-16 right-4 z-50 w-80 space-y-2 pointer-events-none">
      <AnimatePresence>
        {notifications.map((n) => {
          const cfg = LEVEL_STYLES[n.level];
          const Icon = cfg.icon;
          return (
            <motion.div
              key={n.id}
              initial={{ opacity: 0, x: 32, height: 0 }}
              animate={{ opacity: 1, x: 0, height: "auto" }}
              exit={{ opacity: 0, x: 32, height: 0 }}
              transition={{ duration: 0.2 }}
              className="pointer-events-auto"
            >
              <div
                className={cn(
                  "flex items-start gap-2.5 rounded-lg border px-3 py-2.5 shadow-xl",
                  cfg.bg,
                  cfg.border
                )}
              >
                <Icon className={cn("size-4 mt-0.5 shrink-0", cfg.text)} />
                <p className={cn("flex-1 text-xs leading-relaxed", cfg.text)}>
                  {n.message}
                </p>
                <button
                  onClick={() => dismiss(n.id)}
                  className="shrink-0 text-slate-600 hover:text-slate-400 transition-colors"
                >
                  <X className="size-3.5" />
                </button>
              </div>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
