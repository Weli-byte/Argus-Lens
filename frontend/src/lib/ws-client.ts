"use client";

import { config } from "./config";
import type { WSConnectionState, WSMessage } from "@/types";

type MessageHandler<T = unknown> = (payload: T) => void;

interface QueuedMessage {
  type: string;
  payload: unknown;
}

// ---------------------------------------------------------------------------
// ArgusWebSocketClient — production WebSocket with reconnect + heartbeat
// ---------------------------------------------------------------------------

class ArgusWebSocketClient {
  private ws: WebSocket | null = null;
  private state: WSConnectionState = "disconnected";
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private pongTimer: ReturnType<typeof setTimeout> | null = null;
  private latency = 0;
  private pingTs = 0;
  private messageQueue: QueuedMessage[] = [];
  private token: string | null = null;
  private baseUrl: string = "";

  // Typed event listeners — type → Set<handler>
  private listeners: Map<string, Set<MessageHandler<unknown>>> = new Map();
  // State change listeners
  private stateListeners: Set<(s: WSConnectionState) => void> = new Set();

  // ---------------------------------------------------------------------------
  // Connection
  // ---------------------------------------------------------------------------

  connect(url: string, token: string): void {
    this.baseUrl = url;
    this.token = token;
    this._openSocket();
  }

  private _openSocket(): void {
    if (this.ws) {
      this.ws.onopen = null;
      this.ws.onmessage = null;
      this.ws.onclose = null;
      this.ws.onerror = null;
      this.ws.close();
      this.ws = null;
    }

    this._setState("connecting");

    const url = new URL(
      `${this.baseUrl}/api/v1/stream/live`.replace(/^http/, "ws")
    );
    if (this.token) url.searchParams.set("token", this.token);

    const ws = new WebSocket(url.toString());
    this.ws = ws;

    ws.onopen = () => {
      this._setState("connected");
      this.reconnectAttempts = 0;
      this._startHeartbeat();
      this._flushQueue();
    };

    ws.onmessage = (event: MessageEvent<string>) => {
      this._handleMessage(event);
    };

    ws.onclose = () => {
      this._cleanup();
      if (this.state !== "disconnected") {
        this._scheduleReconnect();
      }
    };

    ws.onerror = () => {
      this._setState("error");
    };
  }

  disconnect(): void {
    this._setState("disconnected");
    this._cleanup();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  // ---------------------------------------------------------------------------
  // Message handling
  // ---------------------------------------------------------------------------

  send<T>(type: string, payload: T): void {
    const msg: WSMessage<T> = {
      type,
      payload,
      timestamp: Date.now(),
      trace_id: crypto.randomUUID(),
    };
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    } else {
      this.messageQueue.push({ type, payload });
    }
  }

  private _handleMessage(event: MessageEvent<string>): void {
    let msg: WSMessage<unknown>;
    try {
      msg = JSON.parse(event.data) as WSMessage<unknown>;
    } catch {
      return;
    }

    // Pong handling
    if (msg.type === "pong" || msg.type === "ping") {
      this.latency = Date.now() - this.pingTs;
      if (this.pongTimer) clearTimeout(this.pongTimer);
      this._emit("__latency__", this.latency);
      return;
    }

    this._emit(msg.type, msg.payload);
  }

  // ---------------------------------------------------------------------------
  // Event emitter
  // ---------------------------------------------------------------------------

  on<T>(type: string, handler: MessageHandler<T>): () => void {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, new Set());
    }
    const h = handler as MessageHandler<unknown>;
    this.listeners.get(type)!.add(h);
    return () => this.listeners.get(type)?.delete(h);
  }

  onStateChange(handler: (s: WSConnectionState) => void): () => void {
    this.stateListeners.add(handler);
    return () => this.stateListeners.delete(handler);
  }

  private _emit(type: string, payload: unknown): void {
    this.listeners.get(type)?.forEach((h) => h(payload));
  }

  private _setState(s: WSConnectionState): void {
    this.state = s;
    this.stateListeners.forEach((h) => h(s));
  }

  // ---------------------------------------------------------------------------
  // Heartbeat
  // ---------------------------------------------------------------------------

  private _startHeartbeat(): void {
    this._stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      this.pingTs = Date.now();
      this.send("ping", { ts: this.pingTs });
      this.pongTimer = setTimeout(() => {
        // No pong within 5s — treat as dead
        this.ws?.close();
      }, config.ws.pongTimeout);
    }, config.ws.heartbeatInterval);
  }

  private _stopHeartbeat(): void {
    if (this.heartbeatTimer) clearInterval(this.heartbeatTimer);
    if (this.pongTimer) clearTimeout(this.pongTimer);
  }

  // ---------------------------------------------------------------------------
  // Reconnect
  // ---------------------------------------------------------------------------

  private _scheduleReconnect(): void {
    if (this.reconnectAttempts >= config.ws.reconnectMaxAttempts) {
      this._setState("error");
      return;
    }
    this._setState("reconnecting");
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30_000);
    this.reconnectAttempts++;
    this.reconnectTimer = setTimeout(() => {
      if (this.token) this._openSocket();
    }, delay);
  }

  private _cleanup(): void {
    this._stopHeartbeat();
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
  }

  private _flushQueue(): void {
    while (this.messageQueue.length > 0) {
      const item = this.messageQueue.shift()!;
      this.send(item.type, item.payload);
    }
  }

  // ---------------------------------------------------------------------------
  // Subscription helpers
  // ---------------------------------------------------------------------------

  subscribeToInference(sessionId: string): void {
    this.send("subscribe_inference", { session_id: sessionId });
  }

  subscribeToTemporal(sessionId: string): void {
    this.send("subscribe_temporal", { session_id: sessionId });
  }

  subscribeToWorkers(): void {
    this.send("subscribe_workers", {});
  }

  // ---------------------------------------------------------------------------
  // Getters
  // ---------------------------------------------------------------------------

  getConnectionState(): WSConnectionState {
    return this.state;
  }

  getLatency(): number {
    return this.latency;
  }

  getReconnectAttempts(): number {
    return this.reconnectAttempts;
  }
}

// Singleton instance
let _instance: ArgusWebSocketClient | null = null;

export function getWSClient(): ArgusWebSocketClient {
  if (!_instance) {
    _instance = new ArgusWebSocketClient();
  }
  return _instance;
}

export type { ArgusWebSocketClient };
