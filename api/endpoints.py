from __future__ import annotations

import asyncio
import base64
import io
import logging
import time
from typing import List, Optional

import numpy as np

from monitoring.log_pipeline import logger
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_db
from streaming.websocket import stream_manager

router = APIRouter()

# ---------------------------------------------------------------------------
# Pipeline singleton — created at import, model weights loaded lazily
# ---------------------------------------------------------------------------

try:
    from ai.grounding_dino.inference import GroundingDinoPipeline as _PipelineClass
    _pipeline: Optional[_PipelineClass] = _PipelineClass()
except Exception:
    _pipeline = None  # type: ignore[assignment]


async def _get_pipeline():
    """Return the shared pipeline, loading weights on first call."""
    if _pipeline is None:
        raise HTTPException(status_code=503, detail="AI model unavailable — check server logs")
    if not _pipeline.is_loaded():
        await _pipeline.load_model()
    return _pipeline


# ---------------------------------------------------------------------------
# Turkish ↔ English helpers
# ---------------------------------------------------------------------------

_TR_TO_EN: dict[str, str] = {
    "araba": "car", "otomobil": "car", "arabalar": "car",
    "araç": "vehicle", "araçlar": "vehicle",
    "insan": "person", "insanlar": "person",
    "kişi": "person", "kişiler": "person",
    "adam": "man", "kadın": "woman",
    "çocuk": "child", "bebek": "baby",
    "ev": "house",
    "bina": "building", "binalar": "building",
    "ağaç": "tree", "ağaçlar": "tree",
    "çiçek": "flower", "bitki": "plant",
    "kedi": "cat", "köpek": "dog", "kuş": "bird",
    "at": "horse", "inek": "cow", "fil": "elephant",
    "ayı": "bear", "zebra": "zebra", "zürafa": "giraffe",
    "aslan": "lion", "kaplan": "tiger",
    "masa": "table",
    "sandalye": "chair", "kanepe": "couch",
    "yatak": "bed", "kapı": "door", "pencere": "window",
    "telefon": "phone",
    "bilgisayar": "computer",
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
    "tabela": "sign",
    "köprü": "bridge",
    "hayvan": "animal",
    "mobilya": "furniture",
    "elektronik": "electronics",
    # Colors
    "siyah": "black", "beyaz": "white", "kırmızı": "red", "kirmizi": "red",
    "mavi": "blue", "yeşil": "green", "yesil": "green", "sarı": "yellow", "sari": "yellow",
    "gri": "gray", "turuncu": "orange", "pembe": "pink", "mor": "purple", "kahverengi": "brown",
    # Adjectives
    "büyük": "large", "buyuk": "large", "küçük": "small", "kucuk": "small",
    "genç": "young", "genc": "young", "yaşlı": "old", "yasli": "old",
    "yeni": "new", "eski": "old", "uzun": "tall", "kısa": "short", "kisa": "short",
    # Road / Traffic
    "trafik levhası": "traffic sign", "trafik levhasi": "traffic sign",
    "trafik işareti": "traffic sign", "trafik isareti": "traffic sign",
    "yaya geçidi": "crosswalk", "yaya gecidi": "crosswalk",
    "trafik ışığı": "traffic light", "trafik isigi": "traffic light",
    "trafik ışıkları": "traffic light", "trafik isiklari": "traffic light",
    "levha": "sign", "tabela": "sign", "işaret": "sign", "isaret": "sign",
    "kaldırım": "sidewalk", "kaldirim": "sidewalk",
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
    # Colors
    "black": "siyah", "white": "beyaz", "red": "kırmızı", "blue": "mavi",
    "green": "yeşil", "yellow": "sarı", "gray": "gri", "orange": "turuncu",
    "pink": "pembe", "purple": "mor", "brown": "kahverengi",
    # Adjectives
    "large": "büyük", "small": "küçük", "young": "genç", "old": "yaşlı",
    "new": "yeni", "tall": "uzun", "short": "kısa",
    # Road / Traffic
    "traffic sign": "trafik levhası", "crosswalk": "yaya geçidi",
    "sidewalk": "kaldırım",
}


async def _translate_prompt(prompt: str) -> str:
    """Translate Turkish search terms to English asynchronously using deep-translator with static fallback."""
    parts = [p.strip() for p in prompt.split(",") if p.strip()]
    translated = []
    try:
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source='tr', target='en')
        def _do_translate(text: str) -> str:
            return translator.translate(text)
        for p in parts:
            tr_phrase = await asyncio.to_thread(_do_translate, p)
            translated.append(tr_phrase)
        return ", ".join(translated)
    except Exception as exc:
        logger.warning("Dynamic async translation failed, using static: %s", exc)
        
    for p in parts:
        lower = p.lower()
        if lower in _TR_TO_EN:
            translated.append(_TR_TO_EN[lower])
        else:
            words = lower.split()
            tr_words = [_TR_TO_EN.get(w, w) for w in words]
            translated.append(" ".join(tr_words))
    return ", ".join(translated)


async def _to_turkish(label: str) -> str:
    label_clean = label.lower().strip()
    if label_clean in _EN_TO_TR:
        return _EN_TO_TR[label_clean]
    try:
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source='en', target='tr')
        def _do_translate(text: str) -> str:
            return translator.translate(text)
        return await asyncio.to_thread(_do_translate, label)
    except Exception:
        pass
    words = label_clean.split()
    tr_words = [_EN_TO_TR.get(w, w) for w in words]
    return " ".join(tr_words)


def _matches_color(crop_rgb: np.ndarray, color_name: str) -> bool:
    """Check if the cropped image contains the specified color name using HSV thresholding."""
    if crop_rgb.size == 0:
        return True
    
    import cv2
    hsv = cv2.cvtColor(crop_rgb, cv2.COLOR_RGB2HSV)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    
    color_name = color_name.lower().strip()
    
    if color_name == "yellow":
        mask = (h >= 10) & (h <= 34) & (s >= 40) & (v >= 40)
        pct = float(np.mean(mask))
        logger.info("[Color Filter] yellow pct=%.3f, threshold=0.12", pct)
        return pct > 0.12
        
    elif color_name == "black":
        mask = (v < 55)
        pct = float(np.mean(mask))
        logger.info("[Color Filter] black pct=%.3f, threshold=0.22", pct)
        return pct > 0.22
        
    elif color_name == "white":
        mask = (s < 45) & (v > 175)
        pct = float(np.mean(mask))
        logger.info("[Color Filter] white pct=%.3f, threshold=0.20", pct)
        return pct > 0.20
        
    elif color_name == "red":
        mask = ((h < 12) | (h > 168)) & (s >= 40) & (v >= 40)
        pct = float(np.mean(mask))
        logger.info("[Color Filter] red pct=%.3f, threshold=0.10", pct)
        return pct > 0.10
        
    elif color_name == "blue":
        mask = (h >= 85) & (h <= 135) & (s >= 40) & (v >= 40)
        pct = float(np.mean(mask))
        logger.info("[Color Filter] blue pct=%.3f, threshold=0.10", pct)
        return pct > 0.10
        
    elif color_name == "green":
        mask = (h >= 35) & (h <= 85) & (s >= 35) & (v >= 35)
        pct = float(np.mean(mask))
        logger.info("[Color Filter] green pct=%.3f, threshold=0.10", pct)
        return pct > 0.10
        
    elif color_name == "gray" or color_name == "grey":
        mask = (s < 40) & (v >= 55) & (v <= 180)
        pct = float(np.mean(mask))
        logger.info("[Color Filter] gray pct=%.3f, threshold=0.20", pct)
        return pct > 0.20
        
    return True



# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

COLORS = [
    "#00D4FF", "#7C3AED", "#10B981", "#F59E0B",
    "#EF4444", "#EC4899", "#8B5CF6", "#06B6D4",
    "#84CC16", "#F97316", "#6366F1", "#14B8A6",
    "#F43F5E", "#A855F7", "#22D3EE", "#4ADE80",
]


class DetectRequest(BaseModel):
    image_base64: str
    prompt: str
    confidence_threshold: float = 0.25   # YOLO-World sweet spot (was 0.5 for Grounding DINO)
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


# ---------------------------------------------------------------------------
# /detect
# ---------------------------------------------------------------------------

@router.post("/detect", response_model=DetectResponse)
async def detect_objects(request: DetectRequest):
    """
    POST /api/v1/detect — synchronous zero-shot object detection.
    """
    t0 = time.monotonic()

    # ── Decode image ──────────────────────────────────────────────────────────
    raw = request.image_base64
    if "," in raw:
        raw = raw.split(",", 1)[1]
    try:
        image_bytes = base64.b64decode(raw)
        from PIL import Image as PILImage
        pil_img = PILImage.open(io.BytesIO(image_bytes)).convert("RGB")
        import os
        os.makedirs("scratch", exist_ok=True)
        pil_img.save("scratch/last_detect.png")
        image_np = np.array(pil_img)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Image decode failed: {exc}")

    # ── Translate prompt ──────────────────────────────────────────────────────
    if request.language == "en":
        translated = request.prompt
    elif request.language == "tr":
        translated = await _translate_prompt(request.prompt)
    else:
        # auto mode
        cleaned = request.prompt.lower().strip()
        is_tr = any(c in "ğüşıöçĞÜŞİÖÇ" for c in request.prompt) or any(w in _TR_TO_EN for w in cleaned.replace(",", " ").split())
        if is_tr:
            translated = await _translate_prompt(request.prompt)
        else:
            translated = request.prompt

    # ── Run inference ─────────────────────────────────────────────────────────
    try:
        pipeline = await _get_pipeline()
        result = await pipeline.infer(image_np, translated)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Inference error: {exc}")

    raw_boxes:  list = result.get("boxes",  [])
    raw_labels: list = result.get("labels", [])
    raw_scores: list = result.get("scores", [])
    model_id: str    = result.get("model_id", result.get("model", "unknown"))

    image_h, image_w = image_np.shape[:2]
    image_area = image_w * image_h

    # ── Filter by threshold + per-label confidence + box size ────────────────
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
            box_ratio = (bw * bh) / image_area
            if box_ratio > 0.80:
                logger.info("skip %s oversized box %.1f%%", label, box_ratio * 100)
                continue
            if box_ratio < 0.0001:
                continue

        if label not in label_color:
            label_color[label] = COLORS[len(label_color) % len(COLORS)]

        # ── Color Filtering ───────────────────────────────────────────────────
        color_words = {"yellow", "black", "white", "red", "blue", "green", "gray", "grey"}
        query_words = set(translated.lower().replace(",", " ").split())
        matched_colors = query_words.intersection(color_words)
        
        keep_box = True
        if matched_colors:
            iy1 = max(0, int(y1))
            iy2 = min(image_h, int(y2))
            ix1 = max(0, int(x1))
            ix2 = min(image_w, int(x2))
            if iy2 > iy1 and ix2 > ix1:
                crop = image_np[iy1:iy2, ix1:ix2]
                for color_name in matched_colors:
                    if not _matches_color(crop, color_name):
                        keep_box = False
                        logger.info("Discard box %s due to color mismatch with %r", label, color_name)
                        break
        
        if not keep_box:
            continue

        label_tr = await _to_turkish(label)
        boxes_out.append(BoundingBox(
            x1=x1, y1=y1, x2=x2, y2=y2,
            label=label,
            label_tr=label_tr,
            score=round(sc, 4),
            color=label_color[label],
        ))

    latency = round((time.monotonic() - t0) * 1000, 1)

    logger.info(
        "detect image=%dx%d prompt=%r boxes=%d latency=%.0fms",
        image_w, image_h, translated, len(boxes_out), latency,
    )
    for b in boxes_out:
        bw = b.x2 - b.x1
        bh = b.y2 - b.y1
        logger.debug(
            "  %s score=%.3f [%.0f,%.0f → %.0f,%.0f] area=%.1f%%",
            b.label, b.score, b.x1, b.y1, b.x2, b.y2,
            100 * bw * bh / image_area if image_area > 0 else 0,
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


# ---------------------------------------------------------------------------
# Legacy / other endpoints
# ---------------------------------------------------------------------------

class TemporalRequest(BaseModel):
    sequence: List[float]


@router.post("/temporal/analyze")
async def analyze_temporal(request: TemporalRequest):
    try:
        from ai.temporal_transformer.model import TemporalTransformerModel
        model = TemporalTransformerModel()
        result = model.analyze_sequence(request.sequence)
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/detections")
async def get_detections(db: AsyncSession = Depends(get_db)):
    return {"status": "success", "data": []}


@router.get("/risk-scores")
async def get_risk_scores(db: AsyncSession = Depends(get_db)):
    return {"status": "success", "data": []}


@router.websocket("/stream/live")
async def websocket_endpoint(websocket: WebSocket):
    await stream_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await stream_manager.broadcast_json({"message": f"Echo: {data}"})
    except WebSocketDisconnect:
        stream_manager.disconnect(websocket)
