"use client";

import { useEffect, useRef } from "react";
import { getWSClient } from "@/lib/ws-client";
import { useWSStore } from "@/store/ws-store";
import { useAuthStore } from "@/store/auth-store";
import { getAccessToken } from "@/lib/api-client";
import { config } from "@/lib/config";
import type { WSConnectionState } from "@/types";

export function useWebSocket() {
  const setConnectionState = useWSStore((s) => s.setConnectionState);
  const setLatency = useWSStore((s) => s.setLatency);
  const connectionState = useWSStore((s) => s.connectionState);
  const latency = useWSStore((s) => s.latency);
  const sessionId = useWSStore((s) => s.sessionId);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const connected = useRef(false);

  useEffect(() => {
    if (!isAuthenticated || connected.current) return;
    connected.current = true;

    const client = getWSClient();

    const unsubState = client.onStateChange((s: WSConnectionState) => {
      setConnectionState(s);
    });

    const unsubLatency = client.on<number>("__latency__", (ms) => {
      setLatency(ms);
    });

    const token = getAccessToken() ?? "";
    client.connect(config.api.baseUrl, token);

    return () => {
      unsubState();
      unsubLatency();
      connected.current = false;
    };
  }, [isAuthenticated, setConnectionState, setLatency]);

  return { connectionState, latency, sessionId };
}
