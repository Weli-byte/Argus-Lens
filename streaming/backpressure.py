import asyncio
import time
from monitoring.log_pipeline import logger
from monitoring.prometheus_metrics import DROPPED_FRAMES

class AdaptiveBackpressure:
    """
    Real backpressure system that detects client speed and queue overflow.
    Dynamically reduces FPS / drops frames to prevent OOM on server and 
    lag on the client side.
    """
    def __init__(self, max_queue_size: int = 30, target_fps: int = 15):
        self.max_queue_size = max_queue_size
        self.target_fps = target_fps
        self.frame_interval = 1.0 / target_fps
        self.queue = asyncio.Queue(maxsize=max_queue_size)
        
        self.current_fps = target_fps
        self.last_frame_time = time.time()
        
    async def add_frame(self, frame_data: bytes) -> bool:
        """
        Attempts to add a frame to the queue.
        Returns False if the frame was dropped due to backpressure.
        """
        now = time.time()
        
        # Adaptive FPS Check
        if now - self.last_frame_time < (1.0 / self.current_fps):
            DROPPED_FRAMES.inc()
            return False
            
        try:
            # wait_for adds a tiny block, but if full, throws TimeoutError instantly
            await asyncio.wait_for(self.queue.put(frame_data), timeout=0.01)
            self.last_frame_time = now
            return True
        except (asyncio.TimeoutError, asyncio.QueueFull):
            # Queue Overflow Detection
            logger.warning(f"Backpressure detected! Queue is full ({self.max_queue_size}). Dropping frame.")
            DROPPED_FRAMES.inc()
            
            # Reduce FPS dynamically to recover
            self._reduce_fps()
            return False
            
    def _reduce_fps(self):
        """Reduces FPS by 20% on backpressure, min 1 FPS."""
        old_fps = self.current_fps
        self.current_fps = max(1, int(self.current_fps * 0.8))
        if old_fps != self.current_fps:
            logger.info(f"Dynamically reduced streaming FPS from {old_fps} to {self.current_fps}")

    def recover_fps(self):
        """Called periodically if queue is empty to restore original FPS."""
        if self.queue.empty() and self.current_fps < self.target_fps:
            self.current_fps = min(self.target_fps, self.current_fps + 1)
