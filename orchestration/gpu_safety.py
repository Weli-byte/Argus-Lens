import torch
import asyncio
from typing import AsyncGenerator, Any
from monitoring.log_pipeline import logger

class GPUSafetyManager:
    """
    Prevents race conditions on GPU and manages VRAM fragmentation.
    Essential for multi-request concurrent execution.
    """
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        # We only allow a certain number of concurrent streams per GPU to avoid OOM
        self._lock = asyncio.Lock()
        
    async def get_safe_stream(self) -> Any:
        """
        Yields a CUDA stream safely, preventing simultaneous execution race conditions.
        """
        if self.device == "cpu":
            yield None
            return
            
        stream = torch.cuda.Stream()
        try:
            yield stream
        finally:
            # Synchronize to ensure all ops in this stream are finished before it's deleted/reused
            stream.synchronize()

    async def execute_safely(self, func: callable, *args, **kwargs) -> Any:
        """
        Executes a GPU-heavy function with thread safety and OOM recovery.
        """
        async with self._lock:
            try:
                # Optionally use a stream
                if self.device == "cuda":
                    stream = torch.cuda.Stream()
                    with torch.cuda.stream(stream):
                        result = func(*args, **kwargs)
                    stream.synchronize()
                    return result
                else:
                    return func(*args, **kwargs)
            except RuntimeError as e:
                if "out of memory" in str(e).lower():
                    logger.error("OOM encountered! Initiating emergency recovery.")
                    self.emergency_recovery()
                    raise Exception("Inference failed due to GPU OOM. System recovering.")
                raise e

    def emergency_recovery(self):
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
            logger.info("Emergency GPU memory cleanup executed.")
