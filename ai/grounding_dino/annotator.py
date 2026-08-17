import cv2
import numpy as np
from typing import List, Dict, Any

class FrameAnnotator:
    """
    Renders bounding boxes and labels onto frames.
    """
    @staticmethod
    def draw_detections(cv2_img: np.ndarray, detections: List[Dict[str, Any]]) -> np.ndarray:
        """
        Draws boxes and labels on the image.
        """
        annotated_img = cv2_img.copy()
        
        for det in detections:
            bbox = det["bbox"]
            label = det["label"]
            conf = det["confidence"]
            
            x1, y1, x2, y2 = map(int, bbox)
            
            # Draw Box
            cv2.rectangle(annotated_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            # Draw Label
            text = f"{label} {conf:.2f}"
            (text_width, text_height), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(annotated_img, (x1, y1 - text_height - 5), (x1 + text_width, y1), (0, 255, 0), -1)
            cv2.putText(annotated_img, text, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
            
        return annotated_img
        
    @staticmethod
    def encode_frame(cv2_img: np.ndarray, quality: int = 85) -> bytes:
        """
        Encodes the image to JPEG bytes for streaming.
        """
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        _, buffer = cv2.imencode('.jpg', cv2_img, encode_param)
        return buffer.tobytes()
