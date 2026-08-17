"use client";

import { useEffect, useRef, useState } from "react";
import { useVitalStore } from "@/store/vital-store";
import type { VitalTelemetry } from "@/types";

export function useVitalStream() {
  const addRecord = useVitalStore((s) => s.addRecord);
  const setHistory = useVitalStore((s) => s.setHistory);
  const currentTelemetry = useVitalStore((s) => s.currentTelemetry);
  const history = useVitalStore((s) => s.history);
  
  const [connectionStatus, setConnectionStatus] = useState<
    "connecting" | "connected" | "disconnected"
  >("connecting");
  
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    // 1. Fetch initial history
    const fetchHistory = async () => {
      try {
        const res = await fetch("http://127.0.0.1:8090/api/v1/vitals/history");
        if (res.ok) {
          const data = await res.json();
          setHistory(data);
        }
      } catch (err) {
        console.error("Failed to fetch vital history:", err);
      }
    };

    fetchHistory();

    // 2. Connect WebSocket
    const connect = () => {
      setConnectionStatus("connecting");
      const wsUrl = "ws://127.0.0.1:8090/api/v1/vitals/stream";
      
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnectionStatus("connected");
        console.log("Vital signs WebSocket stream connected.");
      };

      ws.onmessage = (event) => {
        try {
          const data: VitalTelemetry = JSON.parse(event.data);
          addRecord(data);
        } catch (err) {
          console.error("Failed to parse vital telemetry message:", err);
        }
      };

      ws.onclose = () => {
        setConnectionStatus("disconnected");
        console.log("Vital signs WebSocket stream disconnected. Retrying in 3s...");
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, 3000);
      };

      ws.onerror = (err) => {
        console.error("Vital signs WebSocket error:", err);
        ws.close();
      };
    };

    connect();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [addRecord, setHistory]);

  return { currentTelemetry, history, connectionStatus };
}
