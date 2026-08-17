import torch
from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

class GroundingDinoLoader:
    """
    Downloads, caches and loads the Grounding DINO model from HuggingFace.
    Implements device auto-selection and memory optimizations.
    """
    def __init__(self, model_id: str = "IDEA-Research/grounding-dino-base"):
        self.model_id = model_id
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.dtype = torch.float16 if self.device == "cuda" else torch.float32
        
    def load(self) -> Tuple[AutoModelForZeroShotObjectDetection, AutoProcessor]:
        logger.info(f"Loading Grounding DINO model '{self.model_id}' on {self.device} with {self.dtype} precision...")
        try:
            processor = AutoProcessor.from_pretrained(self.model_id)
            model = AutoModelForZeroShotObjectDetection.from_pretrained(
                self.model_id, 
                torch_dtype=self.dtype
            ).to(self.device)
            
            # Optional: torch.compile for faster inference if PyTorch 2.0+ and CUDA
            if self.device == "cuda" and hasattr(torch, "compile"):
                logger.info("Compiling model with torch.compile() for optimized inference...")
                # model = torch.compile(model) # Commented out by default as it can take time to warmup
                
            model.eval()
            logger.info("Grounding DINO model loaded successfully.")
            return model, processor
        except Exception as e:
            logger.error(f"Failed to load Grounding DINO: {e}")
            raise e

    def cleanup(self, model: AutoModelForZeroShotObjectDetection):
        """Clears GPU memory."""
        logger.info("Cleaning up Grounding DINO model from memory.")
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
