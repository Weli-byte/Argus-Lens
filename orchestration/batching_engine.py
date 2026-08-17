import asyncio
import logging
from typing import List, Callable, Any

logger = logging.getLogger(__name__)

class DynamicBatchingEngine:
    """
    Aggregates concurrent inference requests into batches dynamically
    based on max_batch_size and max_wait_time.
    """
    def __init__(self, max_batch_size: int = 4, max_wait_time_ms: int = 50):
        self.max_batch_size = max_batch_size
        self.max_wait_time = max_wait_time_ms / 1000.0
        self.queue = asyncio.Queue()
        self.is_running = False
        self._worker_task = None
        self._inference_callback = None

    def set_inference_callback(self, callback: Callable[[List[Any]], List[Any]]):
        self._inference_callback = callback

    def start(self):
        if not self.is_running:
            self.is_running = True
            self._worker_task = asyncio.create_task(self._process_queue())
            logger.info("Dynamic Batching Engine started.")

    async def stop(self):
        self.is_running = False
        if self._worker_task:
            self._worker_task.cancel()

    async def submit_request(self, data: Any) -> Any:
        future = asyncio.get_event_loop().create_future()
        await self.queue.put((data, future))
        return await future

    async def _process_queue(self):
        while self.is_running:
            batch = []
            try:
                # Wait for at least one item
                item = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                batch.append(item)
                
                # Gather more items up to max_batch_size within max_wait_time
                end_time = asyncio.get_event_loop().time() + self.max_wait_time
                while len(batch) < self.max_batch_size:
                    time_left = end_time - asyncio.get_event_loop().time()
                    if time_left <= 0:
                        break
                    try:
                        item = await asyncio.wait_for(self.queue.get(), timeout=time_left)
                        batch.append(item)
                    except asyncio.TimeoutError:
                        break
                        
                # Execute batch inference
                if self._inference_callback and batch:
                    inputs = [b[0] for b in batch]
                    futures = [b[1] for b in batch]
                    
                    try:
                        # Must be an async callback or run in executor
                        results = await self._inference_callback(inputs)
                        for future, result in zip(futures, results):
                            if not future.done():
                                future.set_result(result)
                    except Exception as e:
                        logger.error(f"Batch inference failed: {e}")
                        for future in futures:
                            if not future.done():
                                future.set_exception(e)
                                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in batch processor: {e}")
