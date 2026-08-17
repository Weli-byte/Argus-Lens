export const config = {
  api: {
    baseUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8090",
    timeout: 30_000,
  },
  ws: {
    url: process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8090",
    reconnectMaxAttempts: 10,
    heartbeatInterval: 30_000,
    pongTimeout: 5_000,
  },
  inference: {
    defaultFpsTarget: 30,
    maxQueueDepth: 100,
  },
  temporal: {
    historyLength: 500,
    anomalyRetention: 50,
  },
  ui: {
    animationDuration: 200,
    chartUpdateInterval: 1_000,
  },
} as const;

export type Config = typeof config;
