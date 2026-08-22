// ---------------------------------------------------------------------------
// WebSocket
// ---------------------------------------------------------------------------

export type WSConnectionState =
  | "connecting"
  | "connected"
  | "disconnected"
  | "reconnecting"
  | "error";

export interface WSMessage<T = unknown> {
  type: string;
  payload: T;
  timestamp: number;
  trace_id: string;
}

export interface WSHeartbeat {
  latency_ms: number;
  server_time: number;
  session_id: string;
}

// ---------------------------------------------------------------------------
// Inference
// ---------------------------------------------------------------------------

export interface BoundingBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface Detection {
  bbox: BoundingBox;
  label: string;
  confidence: number;
  object_id?: string;
}

export interface InferenceResult {
  frame_id: string;
  timestamp: number;
  latency_ms: number;
  detections: Detection[];
  frame_width: number;
  frame_height: number;
  model_id: string;
  gpu_used: boolean;
  status: "success" | "error" | "dropped";
  frame_data?: string;
}

export interface InferenceQueueStatus {
  queued_by_priority: Record<string, number>;
  active_inferences: number;
  max_queue_size: number;
  avg_wait_ms: number;
}

// ---------------------------------------------------------------------------
// Temporal Analytics
// ---------------------------------------------------------------------------

export interface TemporalMetrics {
  heart_rate?: number;
  blink_frequency?: number;
  eye_pressure?: number;
  fatigue_score: number;
  focus_score: number;
  cognitive_load: number;
  neural_latency?: number;
  processing_latency_ms?: number;
  confidence_score?: number;
  timestamp: string;
}

export interface AnomalyEvent {
  id: string;
  type: string;
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  score: number;
  timestamp: string;
  description?: string;
  model_id?: string;
  affected_metric?: string;
  metric_value?: number | string;
}

export interface TemporalForecast {
  risk_level: "SAFE" | "CAUTION" | "WARNING" | "DANGER";
  predicted_events: number;
  time_horizon_minutes: number;
  confidence: number;
  recommendations?: string[];
}

// ---------------------------------------------------------------------------
// GPU
// ---------------------------------------------------------------------------

export interface GPUStatus {
  device_id: number;
  name: string;
  vram_used_mb: number;
  vram_total_mb: number;
  utilization_percent: number;
  temperature_celsius: number;
  power_draw_watts?: number;
}

export interface GPUMetrics {
  gpus: GPUStatus[];
  total_vram_used_mb: number;
  total_vram_total_mb: number;
  avg_utilization: number;
}

// ---------------------------------------------------------------------------
// Workers / Cluster
// ---------------------------------------------------------------------------

export type WorkerState = "active" | "idle" | "overloaded" | "dead";

export interface WorkerInfo {
  worker_id: string;
  state: WorkerState;
  current_load: number;
  capabilities: string[];
  last_heartbeat?: string;
  hostname?: string;
  active_tasks: number;
  queued_tasks: number;
  completed_tasks: number;
  failed_tasks: number;
  cpu_percent?: number;
  memory_percent?: number;
}

export interface ClusterHealth {
  total_workers: number;
  healthy_workers: number;
  degraded_workers: number;
  dead_workers: number;
  cluster_status: "healthy" | "degraded" | "critical";
  workers: WorkerInfo[];
}

// ---------------------------------------------------------------------------
// Models
// ---------------------------------------------------------------------------

export interface ModelVersion {
  model_id: string;
  version: string;
  status: "loaded" | "loading" | "unloaded" | "error";
  accuracy?: number;
  avg_latency_ms?: number;
  total_inferences?: number;
  framework?: string;
  device?: string;
  loaded_at?: string;
  health_score?: number;
}

export interface ModelHealth {
  model_id: string;
  health_score: number;
  confidence_trend: number[];
  drift_detected: boolean;
  last_drift_at?: string;
  inference_count?: number;
  error_count?: number;
  avg_latency_ms?: number;
  error_rate?: number;
}

// ---------------------------------------------------------------------------
// Semantic Search
// ---------------------------------------------------------------------------

export interface SemanticResult {
  id: string;
  content: string;
  similarity_score: number;
  model_id?: string;
  embedding?: number[];
  metadata?: Record<string, unknown>;
  timestamp?: string;
}

export interface SearchQuery {
  query: string;
  top_k: number;
  min_similarity: number;
  filter?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export interface User {
  username: string;
  role: "admin" | "operator" | "viewer";
  id?: string;
  permissions?: string[];
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  expires_in?: number;
  token_type?: string;
  user?: AuthUser;
}

/** /auth/* uçlarının döndürdüğü kullanıcı özeti. */
export interface AuthUser {
  username: string;
  role: string;
  permissions?: string[];
  full_name?: string;
  email?: string;
  phone?: string;
  providers?: string[];
}

export interface AuthProviders {
  google: boolean;
  apple: boolean;
}

// ---------------------------------------------------------------------------
// System Health
// ---------------------------------------------------------------------------

export interface SystemHealth {
  score: number;
  components: {
    db: { score: number };
    redis: { score: number };
    gpu: { score: number };
    workers: { score: number };
  };
  issues: string[];
}

// ---------------------------------------------------------------------------
// System Events
// ---------------------------------------------------------------------------

export interface SystemEvent {
  id: string;
  timestamp: string;
  level: "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";
  module: string;
  message: string;
}

// ---------------------------------------------------------------------------
// Chart helpers
// ---------------------------------------------------------------------------

export interface TimeSeriesPoint {
  time: number;
  [key: string]: number;
}

// ---------------------------------------------------------------------------
// Vital Signs
// ---------------------------------------------------------------------------

export interface VitalRecord {
  heart_rate: number;
  systolic_bp: number;
  diastolic_bp: number;
  spo2: number;
  temperature: number;
  respiratory_rate: number;
  eye_pressure: number;
  tear_glucose: number;
  stress_level: number;
  timestamp: string;
}

export interface NEWS2Result {
  score: number;
  level: "SAFE" | "CAUTION" | "WARNING" | "DANGER";
  status: string;
  details: Record<string, number>;
}

export interface VitalTelemetry {
  vitals: VitalRecord;
  news2: NEWS2Result;
  analysis: {
    risk_score: number;
    anomaly_probability: number;
    trend_direction: "up" | "down" | "stable";
  };
  timestamp: string;
}
