"""
ArgusLens — Standalone Detection Server
========================================
A lightweight FastAPI server that provides *only* the object detection
endpoint. No Redis, PostgreSQL, GPU, or heavy Phase 3/4 modules required.
Now integrated with Grounding DINO for high-precision attribute grounding.

Run:
    uvicorn detect_server:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import time
from typing import Any, List, Optional

import numpy as np
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
logger = logging.getLogger("detect_server")

# ── check for HF transformers library ──
try:
    from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection
    _HF_GD = True
except ImportError:
    _HF_GD = False
    logger.warning("transformers library not found or failed to import. Grounding DINO will be unavailable.")

# ═══════════════════════════════════════════════════════════════════════════
# Detection Pipeline  (Grounding DINO → YOLO-World → YOLO-Standard → Smart Mock)
# ═══════════════════════════════════════════════════════════════════════════

_GD_MODEL = "IDEA-Research/grounding-dino-tiny"
_MODEL_MEDIUM = "yolov8m-worldv2.pt"
_MODEL_SMALL  = "yolov8s-worldv2.pt"
_MODEL_COCO   = "yolov8m.pt"


class DetectionPipeline:
    """Open-vocabulary detection backed by Grounding DINO with YOLO fallbacks."""

    def __init__(self) -> None:
        try:
            import torch
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            self._device = "cpu"

        self._model: Any = None
        self._processor: Any = None
        self._model_type: str = "none"
        self._model_id: str = ""
        self._loaded = False
        self._lock = asyncio.Lock()
        logger.info("DetectionPipeline init  device=%s", self._device)

    # ── model loading ─────────────────────────────────────────────────

    async def load_model(self) -> None:
        async with self._lock:
            if self._loaded:
                return
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._load_best_model)
            self._loaded = True
            logger.info(
                "Pipeline ready  model_type=%s  model_id=%s",
                self._model_type, self._model_id,
            )

    def _load_best_model(self) -> None:
        # 1. Grounding DINO (Hugging Face)
        if _HF_GD:
            try:
                from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection
                import torch
                logger.info("Loading %s on %s...", _GD_MODEL, self._device)
                self._processor = AutoProcessor.from_pretrained(_GD_MODEL)
                self._model = AutoModelForZeroShotObjectDetection.from_pretrained(_GD_MODEL)
                self._model.to(self._device)
                self._model_type = "grounding_dino"
                self._model_id = _GD_MODEL
                logger.info("✓ Loaded Grounding DINO successfully!")
                return
            except Exception as exc:
                logger.warning("Grounding DINO load failed: %s. Trying YOLO-World...", exc)

        # 2. YOLO-World medium (open-vocabulary)
        try:
            from ultralytics import YOLOWorld
            self._model = YOLOWorld(_MODEL_MEDIUM)
            self._model_type = "yolo_world"
            self._model_id   = _MODEL_MEDIUM
            logger.info("✓ Loaded %s  (%s)", _MODEL_MEDIUM, self._device)
            return
        except Exception as exc:
            logger.warning("yolov8m-worldv2 failed: %s", exc)

        # 3. YOLO-World small
        try:
            from ultralytics import YOLOWorld
            self._model = YOLOWorld(_MODEL_SMALL)
            self._model_type = "yolo_world_small"
            self._model_id   = _MODEL_SMALL
            logger.info("✓ Loaded fallback %s", _MODEL_SMALL)
            return
        except Exception as exc:
            logger.warning("yolov8s-worldv2 failed: %s", exc)

        # 4. Standard YOLO 80-class
        try:
            from ultralytics import YOLO
            self._model = YOLO(_MODEL_COCO)
            self._model_type = "yolo_standard"
            self._model_id   = _MODEL_COCO
            logger.warning("Using standard YOLO (no open vocabulary)")
            return
        except Exception as exc:
            logger.error("All YOLO loads failed: %s", exc)

        # 5. Smart mock — always works
        self._model_type = "mock"
        self._model_id   = "smart_mock"
        logger.info("Using smart mock (no model available)")

    # ── inference ─────────────────────────────────────────────────────

    async def infer(self, image: np.ndarray, prompt: str) -> dict[str, Any]:
        if not self._loaded:
            await self.load_model()

        t0 = time.monotonic()
        try:
            if self._model_type == "grounding_dino":
                result = await self._infer_grounding_dino(image, prompt)
            elif self._model_type in ("yolo_world", "yolo_world_small"):
                result = await self._infer_yolo_world(image, prompt)
            elif self._model_type == "yolo_standard":
                result = await self._infer_yolo_standard(image, prompt)
            else:
                result = self._smart_mock(image, prompt)
        except Exception as exc:
            logger.error("Inference error, falling back to mock: %s", exc)
            result = self._smart_mock(image, prompt)

        result["latency_ms"] = round((time.monotonic() - t0) * 1000, 1)
        result["model_id"]   = self._model_id
        return result

    async def _infer_grounding_dino(self, image: np.ndarray, prompt: str) -> dict[str, Any]:
        # Format comma-separated classes to period-separated prompts
        terms = [t.strip().lower() for t in prompt.split(",") if t.strip()]
        if not terms:
            terms = ["object"]
        formatted_prompt = " . ".join(terms) + " ."

        from PIL import Image as PILImage
        pil_img = PILImage.fromarray(image)

        loop = asyncio.get_event_loop()

        def _run():
            import torch
            inputs = self._processor(images=pil_img, text=formatted_prompt, return_tensors="pt").to(self._device)
            with torch.no_grad():
                outputs = self._model(**inputs)
            
            h, w = image.shape[:2]
            # Use lower threshold to capture candidate boxes; post-filtering will clean them
            results = self._processor.post_process_grounded_object_detection(
                outputs,
                threshold=0.10,
                target_sizes=[(h, w)]
            )
            return results[0]

        result = await loop.run_in_executor(None, _run)

        boxes_out = []
        labels_out = []
        scores_out = []

        for box, score, label in zip(result["boxes"], result["scores"], result["labels"]):
            coords = box.cpu().tolist()
            boxes_out.append([round(coords[0], 1), round(coords[1], 1), round(coords[2], 1), round(coords[3], 1)])
            labels_out.append(label.strip())
            scores_out.append(round(float(score.item()), 3))

        return {"boxes": boxes_out, "labels": labels_out, "scores": scores_out}

    async def _infer_yolo_world(self, image: np.ndarray, prompt: str) -> dict[str, Any]:
        classes = [c.strip().lower() for c in prompt.split(",") if c.strip()] or ["object"]
        self._model.set_classes(classes)

        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None,
            lambda: self._model.predict(
                source=image,
                conf=0.25,
                iou=0.45,
                max_det=50,
                verbose=False,
                device=self._device if self._device != "cpu" else None,
            ),
        )
        return self._parse_results(results, image, classes, coco_names=None)

    async def _infer_yolo_standard(self, image: np.ndarray, prompt: str) -> dict[str, Any]:
        prompt_terms = [c.strip().lower() for c in prompt.split(",") if c.strip()]

        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None,
            lambda: self._model.predict(
                source=image, conf=0.25, iou=0.45, max_det=50, verbose=False,
            ),
        )
        coco_names: dict[int, str] = self._model.names
        return self._parse_results(results, image, prompt_terms, coco_names)

    def _parse_results(
        self,
        results: Any,
        image: np.ndarray,
        classes: list[str],
        coco_names: dict[int, str] | None,
    ) -> dict[str, Any]:
        h, w = image.shape[:2]
        area = w * h
        boxes, labels, scores = [], [], []

        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                cid = int(box.cls[0].cpu())
                if coco_names is not None:
                    label = coco_names.get(cid, "object").lower()
                    if classes and not any(t in label or label in t for t in classes):
                        continue
                else:
                    label = classes[cid] if cid < len(classes) else "object"

                coords = box.xyxy[0].cpu().tolist()
                x1, y1 = max(0.0, coords[0]), max(0.0, coords[1])
                x2, y2 = min(float(w), coords[2]), min(float(h), coords[3])
                bw, bh = x2 - x1, y2 - y1

                if bw < 8 or bh < 8:
                    continue
                if area > 0 and (bw * bh) / area > 0.80:
                    continue

                conf = round(float(box.conf[0].cpu()), 3)
                boxes.append([round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)])
                labels.append(label)
                scores.append(conf)

        return {"boxes": boxes, "labels": labels, "scores": scores}

    def _smart_mock(self, image: np.ndarray, prompt: str) -> dict[str, Any]:
        logger.warning("Using mock inference — no model loaded")
        labels = [p.strip() for p in prompt.split(",") if p.strip()][:2] or ["object"]
        h, w = image.shape[:2] if image.ndim >= 2 else (480, 640)
        regions = [
            [w * 0.15, h * 0.20, w * 0.45, h * 0.55],
            [w * 0.55, h * 0.20, w * 0.85, h * 0.55],
        ]
        boxes, lbls, scs = [], [], []
        for i, lbl in enumerate(labels):
            boxes.append([float(v) for v in regions[i % len(regions)]])
            lbls.append(lbl)
            scs.append(round(0.82 - i * 0.07, 2))
        return {"boxes": boxes, "labels": lbls, "scores": scs}

    def is_loaded(self) -> bool:
        return self._loaded

    def get_stats(self) -> dict[str, Any]:
        return {
            "loaded": self._loaded,
            "device": self._device,
            "model_type": self._model_type,
            "model_id": self._model_id,
            "open_vocabulary": self._model_type in ("grounding_dino", "yolo_world", "yolo_world_small"),
        }


# ═══════════════════════════════════════════════════════════════════════════
# Turkish ↔ English translation tables
# ═══════════════════════════════════════════════════════════════════════════

_TR_TO_EN: dict[str, str] = {
    "araba": "car", "otomobil": "car", "arabalar": "car",
    "araç": "vehicle", "araçlar": "vehicle",
    "insan": "person", "insanlar": "person",
    "kişi": "person", "kişiler": "person",
    "adam": "man", "kadın": "woman",
    "çocuk": "child", "bebek": "baby",
    "ev": "house", "bina": "building", "binalar": "building",
    "ağaç": "tree", "ağaçlar": "tree",
    "çiçek": "flower", "bitki": "plant",
    "kedi": "cat", "köpek": "dog", "kuş": "bird",
    "at": "horse", "inek": "cow", "fil": "elephant",
    "ayı": "bear", "zebra": "zebra", "zürafa": "giraffe",
    "aslan": "lion", "kaplan": "tiger",
    "masa": "table", "sandalye": "chair", "kanepe": "couch",
    "yatak": "bed", "kapı": "door", "pencere": "window",
    "telefon": "phone", "bilgisayar": "computer",
    "kitap": "book", "şişe": "bottle", "bardak": "cup",
    "yiyecek": "food", "ekmek": "bread", "meyve": "fruit",
    "yol": "road", "trafik": "traffic",
    "kamyon": "truck", "otobüs": "bus",
    "motosiklet": "motorcycle", "bisiklet": "bicycle",
    "uçak": "airplane", "gemi": "ship",
    "dağ": "mountain", "göl": "lake", "deniz": "sea",
    "güneş": "sun", "bulut": "cloud",
    "çanta": "bag", "ayakkabı": "shoe",
    "gözlük": "glasses", "şapka": "hat", "saat": "clock",
    "yüz": "face", "el": "hand", "göz": "eye",
    "tabela": "sign", "köprü": "bridge",
    "hayvan": "animal", "mobilya": "furniture",
    "elektronik": "electronics",
    "trafik lambası": "traffic light", "trafik ışığı": "traffic light",
    "dur işareti": "stop sign",
    "yaya": "pedestrian", "yayalar": "pedestrian",
    "taksi": "taxi", "minibüs": "minibus",
}

_EN_TO_TR: dict[str, str] = {
    "person": "kişi", "man": "adam", "woman": "kadın",
    "child": "çocuk", "baby": "bebek",
    "car": "araba", "vehicle": "araç", "automobile": "araba",
    "truck": "kamyon", "bus": "otobüs", "motorcycle": "motosiklet",
    "bicycle": "bisiklet", "airplane": "uçak", "boat": "tekne",
    "house": "ev", "home": "ev", "building": "bina",
    "tree": "ağaç", "flower": "çiçek", "plant": "bitki",
    "cat": "kedi", "dog": "köpek", "bird": "kuş",
    "horse": "at", "cow": "inek", "elephant": "fil",
    "bear": "ayı", "giraffe": "zürafa", "zebra": "zebra",
    "lion": "aslan", "tiger": "kaplan",
    "chair": "sandalye", "table": "masa", "desk": "masa",
    "couch": "kanepe", "sofa": "kanepe",
    "bed": "yatak", "door": "kapı", "window": "pencere",
    "phone": "telefon", "mobile": "telefon",
    "laptop": "dizüstü bilgisayar", "computer": "bilgisayar",
    "book": "kitap", "bottle": "şişe", "cup": "bardak",
    "road": "yol", "street": "sokak",
    "traffic light": "trafik ışığı",
    "stop sign": "dur işareti", "sign": "tabela",
    "bench": "bank", "bridge": "köprü",
    "backpack": "sırt çantası", "umbrella": "şemsiye",
    "handbag": "el çantası", "shoe": "ayakkabı",
    "glasses": "gözlük", "hat": "şapka",
    "clock": "saat", "watch": "saat",
    "face": "yüz", "hand": "el", "eye": "göz",
    "food": "yiyecek", "fruit": "meyve", "vegetable": "sebze",
    "bread": "ekmek",
    "mountain": "dağ", "lake": "göl", "sea": "deniz",
    "pedestrian": "yaya", "taxi": "taksi",
}


def _translate_prompt(prompt: str) -> str:
    parts = [p.strip() for p in prompt.split(",") if p.strip()]
    return ", ".join(_TR_TO_EN.get(p.lower(), p) for p in parts)


def _to_turkish(label: str) -> str:
    return _EN_TO_TR.get(label.lower().strip(), label)


# ═══════════════════════════════════════════════════════════════════════════
# Pydantic models  (identical to the original API contract)
# ═══════════════════════════════════════════════════════════════════════════

COLORS = [
    "#00D4FF", "#7C3AED", "#10B981", "#F59E0B",
    "#EF4444", "#EC4899", "#8B5CF6", "#06B6D4",
    "#84CC16", "#F97316", "#6366F1", "#14B8A6",
    "#F43F5E", "#A855F7", "#22D3EE", "#4ADE80",
]


class DetectRequest(BaseModel):
    image_base64: str
    prompt: str
    confidence_threshold: float = 0.15  # Default threshold lowered for GD's zero-shot calibration
    language: str = "auto"


class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    label: str
    label_tr: str
    score: float
    color: str


class DetectResponse(BaseModel):
    boxes: List[BoundingBox]
    total_found: int
    latency_ms: float
    model_used: str
    prompt_used: str
    image_width: Optional[int] = None
    image_height: Optional[int] = None


# ═══════════════════════════════════════════════════════════════════════════
# FastAPI application
# ═══════════════════════════════════════════════════════════════════════════

pipeline = DetectionPipeline()

app = FastAPI(
    title="ArgusLens Detection Server",
    version="1.0.0",
    description="Standalone detection API for ArgusLens frontend",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Startup: pre-load the model ──────────────────────────────────────────

@app.on_event("startup")
async def _startup() -> None:
    logger.info("🚀 ArgusLens Detection Server starting...")
    asyncio.create_task(pipeline.load_model())


# ── Health ────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    stats = pipeline.get_stats()
    return {"status": "healthy", "version": "1.0.0", "gpu": stats}


@app.get("/health/score")
def health_score():
    return {
        "overall_score": 95 if pipeline.is_loaded() else 50,
        "components": {
            "model": {"status": "healthy" if pipeline.is_loaded() else "loading"},
            "api": {"status": "healthy"},
        },
    }


# ── Auth stub (frontend expects these) ──────────────────────────────────

@app.post("/api/v1/auth/token")
async def auth_token():
    """Stub — returns a dummy token so the frontend can proceed."""
    return {
        "access_token": "dev-token-arguslens",
        "refresh_token": "dev-refresh-arguslens",
        "token_type": "bearer",
    }


@app.post("/api/v1/auth/login")
async def auth_login():
    return await auth_token()


@app.post("/api/v1/auth/refresh")
async def auth_refresh():
    return await auth_token()


# ── System stubs ─────────────────────────────────────────────────────────

@app.get("/api/v1/gpu/metrics")
def gpu_metrics():
    return {"gpu_count": 0, "gpus": [], "status": "no_gpu"}


@app.get("/api/v1/cluster/health")
def cluster_health():
    return {"status": "healthy", "workers": 1, "active": 1}


@app.get("/api/v1/models")
def list_models():
    stats = pipeline.get_stats()
    return {
        "models": [
            {
                "id": stats["model_id"],
                "name": stats["model_id"],
                "type": stats["model_type"],
                "loaded": stats["loaded"],
                "device": stats["device"],
            }
        ]
    }


@app.get("/api/v1/inference/queue-status")
def queue_status():
    return {"pending": 0, "processing": 0, "completed": 0}


@app.get("/api/v1/system/events")
def system_events():
    return {"events": []}


@app.get("/api/v1/monitoring/model-health/{model_id}")
def model_health(model_id: str):
    return {"model_id": model_id, "health_score": 0.95, "status": "healthy"}


# ── Object Detection  ────────────────────────────────────────────────────

@app.post("/api/v1/detect", response_model=DetectResponse)
async def detect_objects(request: DetectRequest):
    """
    POST /api/v1/detect — zero-shot object detection.
    Accepts base64-encoded image + comma-separated prompt.
    """
    t0 = time.monotonic()

    # ── Decode image ──
    raw = request.image_base64
    if "," in raw:
        raw = raw.split(",", 1)[1]
    try:
        image_bytes = base64.b64decode(raw)
        from PIL import Image as PILImage
        pil_img = PILImage.open(io.BytesIO(image_bytes)).convert("RGB")
        image_np = np.array(pil_img)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Image decode failed: {exc}")

    # ── Translate prompt ──
    translated = _translate_prompt(request.prompt)
    logger.info("Detect  prompt=%r → %r  threshold=%.2f", request.prompt, translated, request.confidence_threshold)

    # ── Run inference ──
    try:
        result = await pipeline.infer(image_np, translated)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Inference error: {exc}")

    raw_boxes  = result.get("boxes", [])
    raw_labels = result.get("labels", [])
    raw_scores = result.get("scores", [])
    model_id   = result.get("model_id", "unknown")

    image_h, image_w = image_np.shape[:2]
    image_area = image_w * image_h

    # ── Build BoundingBox list ──
    label_color: dict[str, str] = {}
    boxes_out: list[BoundingBox] = []

    for box, label, score in zip(raw_boxes, raw_labels, raw_scores):
        sc = float(score)
        if sc < request.confidence_threshold:
            continue
        if not (isinstance(box, (list, tuple)) and len(box) >= 4):
            continue

        x1, y1, x2, y2 = float(box[0]), float(box[1]), float(box[2]), float(box[3])
        bw, bh = x2 - x1, y2 - y1

        if bw < 5 or bh < 5:
            continue
        if image_area > 0:
            ratio = (bw * bh) / image_area
            # Allow larger ratios for buildings/floors, but protect against full image bounding box
            if ratio > 0.95 or ratio < 0.001:
                continue

        if label not in label_color:
            label_color[label] = COLORS[len(label_color) % len(COLORS)]

        boxes_out.append(BoundingBox(
            x1=x1, y1=y1, x2=x2, y2=y2,
            label=label,
            label_tr=_to_turkish(label),
            score=round(sc, 4),
            color=label_color[label],
        ))

    latency = round((time.monotonic() - t0) * 1000, 1)

    logger.info(
        "Detect  image=%dx%d  prompt=%r  found=%d  latency=%.0fms  model=%s",
        image_w, image_h, translated, len(boxes_out), latency, model_id,
    )

    return DetectResponse(
        boxes=boxes_out,
        total_found=len(boxes_out),
        latency_ms=latency,
        model_used=model_id,
        prompt_used=translated,
        image_width=image_w,
        image_height=image_h,
    )


# ── WebSocket (keeps frontend happy — no more "Reconnecting") ────────────

@app.websocket("/api/v1/stream/live")
async def websocket_live(ws: WebSocket):
    """
    Minimal WebSocket endpoint that keeps the connection alive.
    Responds to ping/pong and echoes unknown frames.
    """
    await ws.accept()
    logger.info("WebSocket connected")
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type", "")

            if msg_type == "ping":
                await ws.send_json({"type": "pong", "timestamp": time.time()})

            elif msg_type in ("start_stream", "stop_stream"):
                await ws.send_json({
                    "type": "stream_ack",
                    "payload": {"status": "ok", "action": msg_type},
                    "timestamp": time.time(),
                })

            elif msg_type.startswith("subscribe_"):
                await ws.send_json({
                    "type": "subscription_ack",
                    "payload": {"channel": msg_type, "status": "ok"},
                    "timestamp": time.time(),
                })

            else:
                await ws.send_json({
                    "type": "ack",
                    "payload": msg,
                    "timestamp": time.time(),
                })

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as exc:
        logger.warning("WebSocket error: %s", exc)


# ═══════════════════════════════════════════════════════════════════════════
# CLI entry point
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("detect_server:app", host="0.0.0.0", port=8000, reload=True)
