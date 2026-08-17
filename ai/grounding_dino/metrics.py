import time
from typing import List

class InferenceMetrics:
    """
    Tracks inference latencies and FPS.
    """
    def __init__(self, history_size: int = 100):
        self.latencies: List[float] = []
        self.history_size = history_size

    def add_latency(self, latency_ms: float):
        self.latencies.append(latency_ms)
        if len(self.latencies) > self.history_size:
            self.latencies.pop(0)

    def get_average_fps(self) -> float:
        if not self.latencies:
            return 0.0
        avg_latency = sum(self.latencies) / len(self.latencies)
        return 1000.0 / avg_latency if avg_latency > 0 else 0.0
