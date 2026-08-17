import asyncio
from monitoring.log_pipeline import logger

class ConcurrencyManager:
    """
    Semaphore-based concurrency limits to protect the system from being overwhelmed
    by burst requests (e.g. 1000 users hitting the detect endpoint simultaneously).
    """
    def __init__(self, max_concurrent_inferences: int = 4):
        # Allow max 4 concurrent model executions to protect GPU memory
        self.semaphore = asyncio.Semaphore(max_concurrent_inferences)
        self.max_queue_wait = 10.0 # seconds before timeout

    async def acquire(self):
        """Attempts to acquire the semaphore with a timeout to prevent deadlocks."""
        try:
            await asyncio.wait_for(self.semaphore.acquire(), timeout=self.max_queue_wait)
            logger.info("Concurrency slot acquired.")
            return True
        except asyncio.TimeoutError:
            logger.error(f"Inference request timed out waiting for concurrency slot.")
            return False

    def release(self):
        self.semaphore.release()
        logger.info("Concurrency slot released.")
