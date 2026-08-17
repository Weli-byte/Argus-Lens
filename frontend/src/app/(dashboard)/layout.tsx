"use client";

import React, { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { useAuthStore } from "@/store/auth-store";
import Sidebar from "@/components/layout/Sidebar";
import TopBar from "@/components/layout/TopBar";
import AlertSystem from "@/components/global/AlertSystem";
import KeyboardShortcuts from "@/components/global/KeyboardShortcuts";
import SystemNotification from "@/components/global/SystemNotification";
import CustomCursor from "@/components/global/CustomCursor";
import CommandPalette from "@/components/global/CommandPalette";
import { useWebSocket } from "@/hooks/useWebSocket";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const router = useRouter();
  const pathname = usePathname();
  // Wait for zustand persist hydration before evaluating auth,
  // otherwise every hard reload flashes /login and loses the deep link.
  const [hydrated, setHydrated] = React.useState(false);

  useWebSocket();

  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (hydrated && !isAuthenticated) {
      router.replace("/login");
    }
  }, [hydrated, isAuthenticated, router]);

  if (!hydrated || !isAuthenticated) return null;

  return (
    <div className="relative flex h-full overflow-hidden">
      {/* Ambient blueprint grid */}
      <div aria-hidden className="ambient-grid pointer-events-none fixed inset-0 z-0" />

      <Sidebar />
      <div className="relative z-10 flex flex-col flex-1 min-w-0 overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-y-auto overflow-x-hidden p-6">
          <motion.div
            key={pathname}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: "easeOut" }}
            className="h-full"
          >
            {children}
          </motion.div>
        </main>
      </div>
      <AlertSystem />
      <KeyboardShortcuts />
      <SystemNotification />
      <CustomCursor />
      <CommandPalette />
    </div>
  );
}
