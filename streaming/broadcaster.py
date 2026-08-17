import asyncio
from fastapi import WebSocket
import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)

class FPSController:
    """
    Adaptive FPS mechanism to prevent streaming backpressure.
    Drops frames if processing/network falls behind.
    """
    def __init__(self, target_fps: int = 15):
        self.target_fps = target_fps
        self.frame_interval = 1.0 / target_fps
        self.last_sent_time = 0.0

    def should_skip_frame(self, current_time: float) -> bool:
        if current_time - self.last_sent_time < self.frame_interval:
            return True
        return False
        
    def update_sent_time(self, current_time: float):
        self.last_sent_time = current_time

class StreamingBroadcaster:
    """
    Low latency websocket broadcaster with frame compression.
    """
    def __init__(self):
        self.connections = set()
        
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.add(websocket)
        
    def disconnect(self, websocket: WebSocket):
        self.connections.remove(websocket)
        
    async def broadcast_frame(self, cv2_img: np.ndarray, quality: int = 75):
        """Compresses and sends frame to all connected clients."""
        if not self.connections:
            return
            
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        _, buffer = cv2.imencode('.jpg', cv2_img, encode_param)
        frame_bytes = buffer.tobytes()
        
        disconnected = set()
        for conn in self.connections:
            try:
                await conn.send_bytes(frame_bytes)
            except Exception as e:
                logger.warning(f"Failed to send to websocket, disconnecting: {e}")
                disconnected.add(conn)
                
        for conn in disconnected:
            self.disconnect(conn)
