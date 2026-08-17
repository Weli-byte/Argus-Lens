"""
GroundingDinoEngine — lazy-loaded inference engine.

Model weights are NOT downloaded at __init__ time.  Call load() explicitly
(or rely on the first predict() call to trigger loading) so that uvicorn
can complete startup without blocking on a multi-hundred-MB HuggingFace download.
"""

import time
import logging
from typing import Any, Dict, List

import torch
import torchvision

# Pre-import transformers (and its lazy deps) in the main thread to avoid
# circular-import / KeyError race conditions when first imported from a
# background thread pool executor.
try:
    import transformers as _transformers_preload  # noqa: F401
    # accelerate is lazily imported by transformers internals; import it here
    # so its module-level state is fully initialised before any thread loads it.
    import accelerate as _accelerate_preload  # noqa: F401
    # Eagerly trigger the auto-model registry so it doesn't race in a thread.
    from transformers import AutoModelForZeroShotObjectDetection as _auto_preload  # noqa: F401
except Exception:
    pass

logger = logging.getLogger(__name__)

_MODEL_ID = "IDEA-Research/grounding-dino-base"


class GroundingDinoEngine:
    """
    Lazy-loading GroundingDINO inference engine.
    Thread-safe: model loading is guarded by a lock.
    """

    def __init__(
        self,
        confidence_threshold: float = 0.35,
        nms_threshold: float = 0.5,
        model_id: str = _MODEL_ID,
    ) -> None:
        self.confidence_threshold = confidence_threshold
        self.nms_threshold = nms_threshold
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model_id = model_id
        self.model = None
        self.processor = None
        self._loaded = False
        # Keep loader reference for backwards-compat attributes
        self.loader = _LoaderCompat(model_id, self.device)

    # ------------------------------------------------------------------
    # Explicit load (called by main.py lifespan via run_in_executor)
    # ------------------------------------------------------------------

    def load(self) -> bool:
        """Download and initialise the model. Returns True on success."""
        if self._loaded:
            return True
        from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor

        dtype = torch.float16 if self.device == "cuda" else torch.float32
        for mid in (self._model_id, "facebook/detr-resnet-50"):
            try:
                logger.info("grounding_dino_engine loading model_id=%s device=%s", mid, self.device)
                self.processor = AutoProcessor.from_pretrained(mid)
                self.model = AutoModelForZeroShotObjectDetection.from_pretrained(
                    mid, torch_dtype=dtype
                ).to(self.device)
                self.model.eval()
                self._model_id = mid
                self.loader.model_id = mid
                self._loaded = True
                logger.info("grounding_dino_engine loaded model_id=%s", mid)
                return True
            except Exception as exc:
                logger.warning("grounding_dino_engine load_failed model_id=%s: %s", mid, exc)

        logger.error("grounding_dino_engine all models failed — running in stub mode")
        return False

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def predict(self, image_bytes: bytes, prompt: str) -> Dict[str, Any]:
        if not self._loaded:
            self.load()

        start = time.perf_counter()

        if not self._loaded:
            # Stub response if loading permanently failed
            return {
                "detections": [],
                "latency_ms": 0.0,
                "fps": 0.0,
                "device": self.device,
                "model_version": "stub",
                "timestamp": time.time(),
                "error": "model_not_loaded",
            }

        from ai.grounding_dino.processor import InferenceProcessor

        pil_img, _ = InferenceProcessor.preprocess_image(image_bytes)
        formatted_prompt = InferenceProcessor.format_prompt(prompt)

        inputs = self.processor(
            images=pil_img, text=formatted_prompt, return_tensors="pt"
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)

        target_sizes = [pil_img.size[::-1]]
        results = self.processor.image_processor.post_process_object_detection(
            outputs,
            threshold=self.confidence_threshold,
            target_sizes=target_sizes,
        )[0]

        boxes = results["boxes"]
        scores = results["scores"]
        labels_indices = results["labels"]

        keep = torchvision.ops.nms(boxes, scores, self.nms_threshold)
        final_boxes = boxes[keep].cpu().numpy().tolist()
        final_scores = scores[keep].cpu().numpy().tolist()
        final_labels = [
            formatted_prompt.split(".")[idx].strip()
            for idx in labels_indices[keep].cpu().numpy()
        ]

        latency_ms = (time.perf_counter() - start) * 1000
        detections = [
            {"label": lbl, "confidence": round(sc, 4), "bbox": [round(b, 2) for b in box]}
            for lbl, sc, box in zip(final_labels, final_scores, final_boxes)
        ]

        return {
            "detections": detections,
            "latency_ms": round(latency_ms, 2),
            "fps": round(1000 / latency_ms, 2) if latency_ms > 0 else 0,
            "device": self.device,
            "model_version": self._model_id,
            "timestamp": time.time(),
        }


class _LoaderCompat:
    """Minimal attribute shim so legacy code that reads loader.model_id still works."""
    def __init__(self, model_id: str, device: str) -> None:
        self.model_id = model_id
        self.device = device
