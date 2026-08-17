"use client";

import React from "react";
import CinematicSection from "@/components/ui/CinematicSection";

export default function CommandCenterPage() {
  // Negative margin cancels the layout's main padding so the cinematic
  // panels run edge-to-edge as the landing experience.
  return (
    <div className="-m-6">
      <CinematicSection />
    </div>
  );
}
