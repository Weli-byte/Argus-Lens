from PIL import Image
import torch
import cv2
import numpy as np
from typing import Tuple, Dict

class InferenceProcessor:
    """
    Handles preprocessing of images and text for Grounding DINO inference.
    """
    @staticmethod
    def preprocess_image(image_bytes: bytes) -> Tuple[Image.Image, np.ndarray]:
        """Converts raw bytes to PIL Image and raw numpy array for CV2."""
        nparr = np.frombuffer(image_bytes, np.uint8)
        cv2_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if cv2_img is None:
            raise ValueError("Failed to decode image bytes.")
        
        # CV2 uses BGR, PIL uses RGB
        cv2_img_rgb = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(cv2_img_rgb)
        
        return pil_img, cv2_img
        
    @staticmethod
    def format_prompt(prompt: str) -> str:
        """
        Grounding DINO expects prompts to be separated by periods and end with a period.
        E.g., "car, phone, person" -> "car. phone. person."
        """
        items = [p.strip() for p in prompt.split(",") if p.strip()]
        return ". ".join(items) + "."
