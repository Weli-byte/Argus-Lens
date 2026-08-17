import torch
import logging
import gc

logger = logging.getLogger(__name__)

class GPUManager:
    """
    Tracks and manages GPU resources for the AI pipeline.
    """
    @staticmethod
    def get_memory_stats() -> dict:
        if not torch.cuda.is_available():
            return {"device": "cpu", "status": "no_gpu"}
            
        device = torch.cuda.current_device()
        allocated = torch.cuda.memory_allocated(device) / (1024 ** 3) # in GB
        reserved = torch.cuda.memory_reserved(device) / (1024 ** 3)
        total = torch.cuda.get_device_properties(device).total_memory / (1024 ** 3)
        
        return {
            "device": torch.cuda.get_device_name(device),
            "allocated_gb": round(allocated, 2),
            "reserved_gb": round(reserved, 2),
            "total_gb": round(total, 2),
            "utilization_percent": round((allocated / total) * 100, 2)
        }
        
    @staticmethod
    def cleanup():
        """Aggressive memory cleanup to prevent OOM errors."""
        logger.info("Running GPU memory cleanup...")
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
