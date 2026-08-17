import cv2
import asyncio
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

class VideoStreamProcessor:
    """
    OpenCV based real-time video processing system.
    """
    def __init__(self, source: int | str = 0, target_fps: int = 15):
        self.source = source
        self.target_fps = target_fps
        self.is_running = False
        self.cap = None

    def start(self):
        logger.info(f"Starting video capture from {self.source}")
        self.cap = cv2.VideoCapture(self.source)
        if not self.cap.isOpened():
            raise RuntimeError(f"Could not open video source {self.source}")
        self.is_running = True

    def stop(self):
        logger.info("Stopping video capture.")
        self.is_running = False
        if self.cap:
            self.cap.release()

    async def get_frames(self) -> AsyncGenerator[bytes, None]:
        """
        Async generator yielding JPEG encoded frames.
        """
        if not self.cap or not self.cap.isOpened():
            self.start()

        delay = 1.0 / self.target_fps

        try:
            while self.is_running:
                ret, frame = self.cap.read()
                if not ret:
                    logger.warning("Failed to grab frame.")
                    break
                
                # Encode frame to JPEG
                _, buffer = cv2.imencode('.jpg', frame)
                frame_bytes = buffer.tobytes()
                
                yield frame_bytes
                
                # Sleep to maintain target FPS and not block async event loop
                await asyncio.sleep(delay)
        finally:
            self.stop()
