import { create } from "zustand";
import type { WSConnectionState } from "@/types";

interface WSState {
  connectionState: WSConnectionState;
  latency: number | null;
  sessionId: string | null;
  reconnectAttempts: number;
  lastHeartbeat: number;
}

interface WSActions {
  setConnectionState: (s: WSConnectionState) => void;
  setLatency: (ms: number | null) => void;
  setSessionId: (id: string | null) => void;
  setReconnectAttempts: (n: number) => void;
  setLastHeartbeat: (ts: number) => void;
  reset: () => void;
}

const initial: WSState = {
  connectionState: "disconnected",
  latency: null,
  sessionId: null,
  reconnectAttempts: 0,
  lastHeartbeat: 0,
};

export const useWSStore = create<WSState & WSActions>((set) => ({
  ...initial,
  setConnectionState: (s) => set({ connectionState: s }),
  setLatency: (ms) => set({ latency: ms }),
  setSessionId: (id) => set({ sessionId: id }),
  setReconnectAttempts: (n) => set({ reconnectAttempts: n }),
  setLastHeartbeat: (ts) => set({ lastHeartbeat: ts }),
  reset: () => set(initial),
}));
