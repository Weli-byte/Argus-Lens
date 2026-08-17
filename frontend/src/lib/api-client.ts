import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from "axios";
import { config } from "./config";
import type {
  SystemHealth,
  GPUMetrics,
  ClusterHealth,
  ModelVersion,
  ModelHealth,
  SemanticResult,
  SearchQuery,
  InferenceQueueStatus,
  AuthTokens,
  SystemEvent,
  WorkerInfo,
} from "@/types";

// ---------------------------------------------------------------------------
// Token storage — access token in memory only; refresh token via API route
// ---------------------------------------------------------------------------

let _accessToken: string | null = null;
let _isRefreshing = false;
let _refreshQueue: Array<(token: string) => void> = [];

export function setAccessToken(token: string | null) {
  _accessToken = token;
}

export function getAccessToken(): string | null {
  return _accessToken;
}

// ---------------------------------------------------------------------------
// Axios instance
// ---------------------------------------------------------------------------

const http: AxiosInstance = axios.create({
  baseURL: config.api.baseUrl,
  timeout: config.api.timeout,
  headers: { "Content-Type": "application/json" },
});

// Request: attach JWT
http.interceptors.request.use((req: InternalAxiosRequestConfig) => {
  if (_accessToken) {
    req.headers.Authorization = `Bearer ${_accessToken}`;
  }
  return req;
});

// Response: handle 401 → refresh; 503 → circuit-breaker banner
http.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean;
    };

    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;

      if (_isRefreshing) {
        return new Promise<string>((resolve) => {
          _refreshQueue.push(resolve);
        }).then((token) => {
          original.headers.Authorization = `Bearer ${token}`;
          return http(original);
        });
      }

      _isRefreshing = true;
      try {
        const res = await fetch("/api/auth/refresh", { method: "POST" });
        if (!res.ok) throw new Error("Refresh failed");
        const data = (await res.json()) as { access_token: string };
        _accessToken = data.access_token;
        _refreshQueue.forEach((cb) => cb(_accessToken!));
        _refreshQueue = [];
        original.headers.Authorization = `Bearer ${_accessToken}`;
        return http(original);
      } catch {
        _accessToken = null;
        if (typeof window !== "undefined") {
          window.dispatchEvent(new CustomEvent("argus:auth:expired"));
        }
        return Promise.reject(error);
      } finally {
        _isRefreshing = false;
      }
    }

    if (error.response?.status === 503) {
      window.dispatchEvent(
        new CustomEvent("argus:circuit-open", {
          detail: { endpoint: original.url ?? "unknown" },
        })
      );
    }

    return Promise.reject(error);
  }
);

// ---------------------------------------------------------------------------
// API methods
// ---------------------------------------------------------------------------

const api = {
  // Auth
  async login(
    username: string,
    password: string
  ): Promise<AuthTokens> {
    const res = await http.post<AuthTokens>("/api/v1/auth/token", {
      username,
      password,
    });
    return res.data;
  },

  async refreshToken(refreshToken: string): Promise<AuthTokens> {
    const res = await http.post<AuthTokens>("/api/v1/auth/refresh", {
      refresh_token: refreshToken,
    });
    return res.data;
  },

  // System
  async getSystemHealth(): Promise<SystemHealth> {
    const res = await http.get<any>("/health/score");
    const raw = res.data ?? {};
    return {
      score: raw.score ?? 0,
      components: {
        db:      { score: raw.components?.db?.score      ?? 0 },
        redis:   { score: raw.components?.redis?.score   ?? 0 },
        gpu:     { score: raw.components?.gpu?.score     ?? 1 },
        workers: { score: raw.components?.workers?.score ?? 0 },
      },
      issues: Array.isArray(raw.issues) ? raw.issues : [],
    };
  },

  async getSystemEvents(): Promise<SystemEvent[]> {
    const res = await http.get<SystemEvent[]>("/api/v1/system/events");
    return Array.isArray(res.data) ? res.data : [];
  },

  // GPU — backend returns `devices`, frontend expects `gpus`
  async getGPUMetrics(): Promise<GPUMetrics> {
    const res = await http.get<any>("/api/v1/gpu/metrics");
    const raw = res.data ?? {};
    const devices: any[] = raw.gpus ?? raw.devices ?? [];
    return {
      gpus: devices.map((d: any) => ({
        device_id:           d.device_id           ?? 0,
        name:                d.name                ?? "CPU",
        vram_used_mb:        d.vram_used_mb         ?? 0,
        vram_total_mb:       d.vram_total_mb        ?? 0,
        utilization_percent: d.utilization_percent  ?? 0,
        temperature_celsius: d.temperature_celsius  ?? 0,
        power_draw_watts:    d.power_draw_watts,
      })),
      total_vram_used_mb:  raw.total_vram_used_mb  ?? 0,
      total_vram_total_mb: raw.total_vram_total_mb ?? 0,
      avg_utilization:     raw.avg_utilization     ?? 0,
    };
  },

  // Cluster — backend missing cluster_status + several worker fields
  async getClusterHealth(): Promise<ClusterHealth> {
    const res = await http.get<any>("/api/v1/cluster/health");
    const raw = res.data ?? {};
    const workers: WorkerInfo[] = (raw.workers ?? []).map((w: any) => ({
      worker_id:       w.worker_id        ?? "",
      state:           w.state            ?? "idle",
      current_load:    w.current_load     ?? 0,
      capabilities:    w.capabilities     ?? [],
      hostname:        w.hostname,
      last_heartbeat:  w.last_heartbeat,
      active_tasks:    w.active_tasks     ?? 0,
      queued_tasks:    w.queued_tasks     ?? 0,
      completed_tasks: w.completed_tasks  ?? w.inference_count ?? 0,
      failed_tasks:    w.failed_tasks     ?? w.error_count     ?? 0,
      cpu_percent:     w.cpu_percent,
      memory_percent:  w.memory_percent,
    }));
    const total   = raw.total_workers   ?? workers.length;
    const healthy = raw.healthy_workers ?? workers.filter((w) => w.state !== "dead").length;
    const dead    = raw.dead_workers    ?? 0;
    const degraded = raw.degraded_workers ?? 0;
    const derivedStatus: ClusterHealth["cluster_status"] =
      healthy === 0 && total > 0 ? "critical" : dead > 0 || degraded > 0 ? "degraded" : "healthy";
    return {
      total_workers:    total,
      healthy_workers:  healthy,
      degraded_workers: degraded,
      dead_workers:     dead,
      cluster_status:   raw.cluster_status ?? derivedStatus,
      workers,
    };
  },

  async getWorkers(): Promise<WorkerInfo[]> {
    const health = await api.getClusterHealth();
    return health.workers;
  },

  // Models — backend returns version_id/is_active/inference_count; frontend expects version/status/total_inferences
  async getModels(): Promise<ModelVersion[]> {
    const res = await http.get<any[]>("/api/v1/models");
    return (Array.isArray(res.data) ? res.data : []).map((m: any) => ({
      model_id:         m.model_id         ?? m.version_id ?? "unknown",
      version:          m.version          ?? m.version_id ?? "v1.0",
      status:           m.status           ?? (m.is_active ? "loaded" : "unloaded"),
      accuracy:         m.accuracy,
      avg_latency_ms:   m.avg_latency_ms,
      total_inferences: m.total_inferences ?? m.inference_count ?? 0,
      framework:        m.framework,
      device:           m.device,
      loaded_at:        m.loaded_at
        ? (typeof m.loaded_at === "number"
            ? new Date(m.loaded_at * 1000).toISOString()
            : m.loaded_at)
        : undefined,
      health_score:     m.health_score,
    }));
  },

  async getModelHealth(modelId: string): Promise<ModelHealth> {
    const res = await http.get<ModelHealth>(
      `/api/v1/monitoring/model-health/${modelId}`
    );
    return res.data;
  },

  async reloadModel(modelId: string, checkpointPath?: string): Promise<void> {
    await http.post(`/api/v1/models/${modelId}/reload`, {
      checkpoint_path: checkpointPath,
    });
  },

  // Inference queue
  async getInferenceQueueStatus(): Promise<InferenceQueueStatus> {
    const res = await http.get<InferenceQueueStatus>(
      "/api/v1/inference/queue-status"
    );
    return res.data;
  },

  // Semantic search
  async semanticSearch(query: SearchQuery): Promise<SemanticResult[]> {
    const res = await http.post<SemanticResult[]>(
      "/api/v1/embeddings/search",
      query
    );
    return res.data;
  },
} as const;

export const apiClient = api;
export default api;
