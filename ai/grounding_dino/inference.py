"""
ArgusLens — Object Detection Pipeline
Uses YOLO-World for open-vocabulary detection.
YOLO-World: Real-Time Open-Vocabulary Object Detection (CVPR 2024)

Load order:
  1. yolov8m-worldv2.pt  (open-vocabulary, tight boxes, fast)
  2. yolov8s-worldv2.pt  (smaller YOLO-World fallback)
  3. yolov8m.pt          (standard 80-class COCO YOLO, prompt-filtered)
  4. smart mock          (always works)

Class name kept as GroundingDinoPipeline for API compatibility.
"""

from __future__ import annotations

import asyncio
import io
import logging
import time
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

try:
    import torch
    _TORCH = True
except ImportError:
    _TORCH = False

try:
    from PIL import Image as PILImage
    _PIL = True
except ImportError:
    _PIL = False

_MODEL_MEDIUM = "yolov8m-worldv2.pt"
_MODEL_SMALL  = "yolov8s-worldv2.pt"
_MODEL_COCO   = "yolov8m.pt"


def _calculate_iou(box1: list[float], box2: list[float]) -> float:
    xi1 = max(box1[0], box2[0])
    yi1 = max(box1[1], box2[1])
    xi2 = min(box1[2], box2[2])
    yi2 = min(box1[3], box2[3])
    
    inter_area = max(0.0, xi2 - xi1) * max(0.0, yi2 - yi1)
    box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
    box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union_area = box1_area + box2_area - inter_area
    
    if union_area == 0.0:
        return 0.0
    return inter_area / union_area

def _apply_nms(
    boxes: list[list[float]], 
    labels: list[str], 
    scores: list[float], 
    iou_threshold: float = 0.60
) -> tuple[list[list[float]], list[str], list[float]]:
    if not boxes:
        return [], [], []
    keep = []
    indices = sorted(range(len(scores)), key=lambda k: scores[k], reverse=True)
    
    while len(indices) > 0:
        current = indices[0]
        keep.append(current)
        indices = indices[1:]
        
        remaining_indices = []
        for idx in indices:
            if labels[current].lower().strip() == labels[idx].lower().strip():
                iou = _calculate_iou(boxes[current], boxes[idx])
                if iou < iou_threshold:
                    remaining_indices.append(idx)
            else:
                remaining_indices.append(idx)
        indices = remaining_indices
        
    return [boxes[i] for i in keep], [labels[i] for i in keep], [scores[i] for i in keep]


# Konum token'ı komşuluk yarıçapı. <loc_N> görüntüyü 1000 kutucuğa böler;
# ±2 kutucuk 768 px'lik girdide yaklaşık ±1.5 px demektir. Model bir kenardan
# emin olduğu hâlde olasılığı bitişik kutucuklara paylaştırdığı için tek
# token'ın olasılığına bakmak kesinliği olduğundan düşük gösteriyor.
_LOC_NEIGHBOURHOOD = 2


def _detection_confidences(
    tokenizer: Any,
    token_strings: list[str],
    probs: Any,
    target_ids: list[int],
    loc_token_ids: dict[int, int],
) -> list[float]:
    """Her tespit için modelin KENDİ olasılığından güven üret.

    Florence-2 üretici bir modeldir; YOLO gibi bir sınıflandırma başlığı yok,
    dolayısıyla hazır bir "confidence" döndürmez. Önceden buraya sabit 0.95
    yazılıyordu — her nesne aynı oranda görünüyordu, yani ekrandaki sayı
    hiçbir şey ölçmüyordu.

    Modelin `<OD>` çıktısı şuna benzer:

        building<loc_0><loc_0><loc_998><loc_430><loc_0>...car<loc_520>...

    Dikkat: etiket kutu BAŞINA yazılmıyor. Bir etiket bir kez çıkıyor, ardından
    o sınıfa ait tüm kutuların koordinatları geliyor. Ölçülen görselde 32 kutu
    için yalnızca 6 etiket token'ı vardı. Bu yüzden etiket token'ının olasılığı
    kutu başına bir güven olarak kullanılamaz; zaten o olasılık "sınıf doğru
    mu" değil "sırada yeni bir sınıfa mı geçiyorum" kararını yansıtıyor.

    Kutu başına gerçekten elde edilebilen sinyal koordinat kesinliğidir:
    bir tespit = tam olarak 4 konum token'ı, güveni de bu dördünün
    olasılıklarının geometrik ortalaması.

    Her konum token'ında tek olasılık yerine ±`_LOC_NEIGHBOURHOOD` kutucukluk
    toplam kütle alınır. Ölçüm: `<loc_521>` tek başına 0.377, komşularıyla
    0.986 — model kenardan emin, olasılık yalnızca bitişik kutucuklara
    yayılmış. Gerçekten belirsiz kenarlar düşük kalır (`<loc_998>` 0.038 →
    0.039), yani ayırt etme gücü korunur.

    Dönen liste, tespitlerin metinde göründükleri sıradaki güvenleridir;
    Florence-2 son işleme adımı da kutuları aynı sırayla ürettiği için
    indeksler eşleşir.
    """
    import math

    confidences: list[float] = []
    logs: list[float] = []

    for i, tok in enumerate(token_strings):
        if not tok or not tok.startswith("<loc_"):
            continue
        try:
            n = int(tok[5:-1])
        except ValueError:
            continue

        lo = max(0, n - _LOC_NEIGHBOURHOOD)
        hi = min(999, n + _LOC_NEIGHBOURHOOD)
        ids = [loc_token_ids[m] for m in range(lo, hi + 1) if m in loc_token_ids]
        if ids:
            mass = float(probs[i, ids].sum())
        else:
            mass = float(probs[i, target_ids[i]])

        # log(0) korunması
        logs.append(math.log(max(mass, 1e-6)))

        if len(logs) == 4:
            confidences.append(math.exp(sum(logs) / 4.0))
            logs = []

    return confidences


def _clamp_confidence(value: float) -> float:
    """Ekranda %0 ya da %100 göstermek yanıltıcı; uçları kırp."""
    if value != value:  # NaN
        return 0.5
    return max(0.05, min(0.99, value))


def _pick_confidence(confidences: list[float], index: int) -> float:
    """i. tespitin güveni; hizalama tutmazsa listenin ortalamasına düş.

    Token bölütleme ile son işlemenin kutu sayısı normalde eşleşir. Nadiren
    (model bozuk çıktı ürettiğinde) eşleşmezse sabit bir sayı uydurmak yerine
    aynı üretimin ortalama güvenini kullanıyoruz — hâlâ modelden gelen
    gerçek bir değer.
    """
    if not confidences:
        return 0.5
    if index < len(confidences):
        return _clamp_confidence(confidences[index])
    return _clamp_confidence(sum(confidences) / len(confidences))


class GroundingDinoPipeline:
    """
    Open-vocabulary object detection backed by YOLO-World.
    Class name kept for API compatibility with existing endpoints.
    """

    def __init__(
        self,
        device: str | None = None,
        confidence_threshold: float = 0.25,
    ) -> None:
        if _TORCH:
            self._device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self._device = "cpu"
        self._confidence_threshold = confidence_threshold
        self._model: Any = None
        self._florence_processor: Any = None
        self._loc_ids_cache: dict[int, int] | None = None
        self._model_type: str = "none"
        self._model_id: str = ""
        self._loaded = False
        self._lock = asyncio.Lock()
        logger.info("GroundingDinoPipeline init device=%s", self._device)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def load_model(self) -> bool:
        async with self._lock:
            if self._loaded:
                return True
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._load_best_model)
            self._loaded = True
            logger.info("Pipeline ready model_type=%s model_id=%s", self._model_type, self._model_id)
            return True

    def _load_best_model(self) -> None:
        # 1. Microsoft Florence-2 (LoRA or base)
        try:
            from transformers import AutoProcessor, AutoModelForCausalLM
            import os
            import torch
            from peft import PeftModel
            
            florence_model_id = "microsoft/Florence-2-base"
            logger.info("Loading Florence-2 model: %s", florence_model_id)
            
            self._florence_processor = AutoProcessor.from_pretrained(florence_model_id, trust_remote_code=True)
            
            dtype = torch.float32
            base_model = AutoModelForCausalLM.from_pretrained(
                florence_model_id, 
                trust_remote_code=True,
                torch_dtype=dtype
            ).to(self._device)
            
            logger.info("Using pre-trained base Florence-2 model (zero-shot)")
            self._model = base_model
                
            self._model.eval()
            self._model_type = "florence"
            self._model_id = "florence2"
            logger.info("Loaded Florence-2 successfully on %s", self._device)
            return
        except Exception as exc:
            logger.error("Florence-2 load failed: %s", exc)
            self._model_type = "mock"
            self._model_id = "mock"

    # ------------------------------------------------------------------
    # Inference entry point
    # ------------------------------------------------------------------

    async def infer(self, image: np.ndarray, prompt: str) -> dict[str, Any]:
        if not self._loaded:
            await self.load_model()

        t0 = time.monotonic()
        try:
            if self._model_type == "florence":
                result = await self._infer_florence(image, prompt)
            elif self._model_type in ("yolo_world", "yolo_world_small"):
                result = await self._infer_yolo_world(image, prompt)
            elif self._model_type == "yolo_standard":
                result = await self._infer_yolo_standard(image, prompt)
            else:
                result = self._smart_mock(image, prompt)
        except Exception as exc:
            logger.error("infer error: %s", exc)
            result = self._smart_mock(image, prompt)

        result["latency_ms"] = round((time.monotonic() - t0) * 1000, 1)
        result["model_id"]   = self._model_id
        result["device"]     = self._device
        return result

    # ------------------------------------------------------------------
    # Florence-2 inference
    # ------------------------------------------------------------------

    def _loc_token_ids(self) -> dict[int, int]:
        """`<loc_0>`..`<loc_999>` token kimlikleri. Bir kez kurulup saklanır."""
        if self._loc_ids_cache is None:
            tokenizer = self._florence_processor.tokenizer
            table: dict[int, int] = {}
            for n in range(1000):
                tid = tokenizer.convert_tokens_to_ids(f"<loc_{n}>")
                if tid is not None and tid >= 0:
                    table[n] = tid
            self._loc_ids_cache = table
        return self._loc_ids_cache

    def _confidences_for(self, inputs: dict, sequences: Any) -> list[float]:
        """Üretilen dizi için tespit başına güven.

        Üretilen diziyi decoder girdisi olarak modele geri besleriz
        (öğretmen zorlaması) ve her adımdaki tam olasılık dağılımını alırız.

        Neden `generate(output_scores=True)` değil: ışın aramasında dönen
        skorlar kümülatif ışın skorlarıdır ve `beam_indices` ile yeniden
        hizalanmaları gerekir; üstelik yalnızca seçilen token'ın olasılığını
        verir. Bize konum token'ının KOMŞULARININ olasılığı da lazım, o yüzden
        tam dağılım şart. Ek maliyet tek bir ileri geçiş — 3 ışınlı üretim
        döngüsünün yanında ucuz.
        """
        import torch

        try:
            with torch.no_grad():
                fwd = self._model(
                    input_ids=inputs["input_ids"],
                    pixel_values=inputs["pixel_values"],
                    decoder_input_ids=sequences[:, :-1],
                )
            probs = torch.softmax(fwd.logits[0].float(), dim=-1)

            target_ids = sequences[0, 1:].tolist()
            n = min(probs.shape[0], len(target_ids))
            target_ids = target_ids[:n]
            tokens = self._florence_processor.tokenizer.convert_ids_to_tokens(target_ids)

            return _detection_confidences(
                self._florence_processor.tokenizer,
                tokens,
                probs,
                target_ids,
                self._loc_token_ids(),
            )
        except Exception as exc:
            logger.warning("Güven skoru hesaplanamadı: %s", exc)
            return []

    async def _infer_florence(self, image: np.ndarray, prompt: str) -> dict[str, Any]:
        from PIL import Image as PILImage
        import torch
        
        queries = [p.strip() for p in prompt.split(",") if p.strip()]
        if not queries:
            queries = ["object"]
            
        boxes_out: list[list[float]] = []
        labels_out: list[str] = []
        scores_out: list[float] = []
        
        h, w = image.shape[:2]
        pil_img = PILImage.fromarray(image)
        pil_img_resized = pil_img.resize((768, 768), PILImage.Resampling.BILINEAR)
        
        loop = asyncio.get_event_loop()
        
        # ── Setup synonyms for dense OD task ──────────────────────────────────
        od_synonyms = {
            "person": {"person", "people", "man", "woman", "child", "boy", "girl", "passenger", "pedestrian"},
            "car": {"car", "cars", "vehicle", "suv"},
            "taxi": {"taxi", "cab"},
            "bus": {"bus", "buses", "coach"},
            "truck": {"truck", "trucks", "lorry", "van"},
            "motorcycle": {"motorcycle", "motorcycles", "bike"},
            "bicycle": {"bicycle", "bicycles", "bike"},
            "dog": {"dog", "dogs"},
            "cat": {"cat", "cats"},
            "bird": {"bird", "birds"},
            "chair": {"chair", "chairs", "seat"},
            "couch": {"couch", "couches", "sofa", "sofas"},
            "table": {"table", "tables", "dining table"},
        }
        
        run_od = False
        od_queries = set()
        for q in queries:
            q_clean = q.lower().strip()
            for od_key, syn_set in od_synonyms.items():
                if q_clean == od_key or q_clean in syn_set:
                    run_od = True
                    od_queries.add((od_key, q))
        
        # ── 1. Optional Dense OD execution ────────────────────────────────────
        if run_od:
            try:
                task_prompt_od = "<OD>"
                inputs_od = self._florence_processor(
                    text=task_prompt_od, 
                    images=pil_img_resized, 
                    return_tensors="pt"
                )
                inputs_od = {k: v.to(self._device) for k, v in inputs_od.items()}
                
                def _generate_od():
                    with torch.no_grad():
                        return self._model.generate(
                            input_ids=inputs_od["input_ids"],
                            pixel_values=inputs_od["pixel_values"],
                            max_new_tokens=1024,
                            num_beams=3,
                        )
                generated_ids_od = await loop.run_in_executor(None, _generate_od)
                conf_od = self._confidences_for(inputs_od, generated_ids_od)
                generated_text_od = self._florence_processor.batch_decode(generated_ids_od, skip_special_tokens=False)[0]
                result_od = self._florence_processor.post_process_generation(
                    generated_text_od, 
                    task=task_prompt_od, 
                    image_size=(w, h)
                )
                
                grounding_data_od = result_od.get(task_prompt_od, {})
                bboxes_od = grounding_data_od.get("bboxes", [])
                labels_od = grounding_data_od.get("labels", [])
                
                for i, (box, label) in enumerate(zip(bboxes_od, labels_od)):
                    label_clean = label.lower().strip()
                    for od_key, orig_q in od_queries:
                        if label_clean == od_key:
                            boxes_out.append([float(box[0]), float(box[1]), float(box[2]), float(box[3])])
                            labels_out.append(orig_q)
                            scores_out.append(_pick_confidence(conf_od, i))
            except Exception as exc:
                logger.error("Dense OD execution failed: %s", exc)

        # ── 2. Standard Phrase Grounding execution ────────────────────────────
        for q in queries:
            try:
                task_prompt = "<CAPTION_TO_PHRASE_GROUNDING>"
                full_prompt = f"{task_prompt} {q}"
                
                inputs = self._florence_processor(
                    text=full_prompt, 
                    images=pil_img_resized, 
                    return_tensors="pt"
                )
                inputs = {k: v.to(self._device) for k, v in inputs.items()}
                    
                def _generate():
                    with torch.no_grad():
                        return self._model.generate(
                            input_ids=inputs["input_ids"],
                            pixel_values=inputs["pixel_values"],
                            max_new_tokens=1024,
                            num_beams=3,
                        )

                generated_ids = await loop.run_in_executor(None, _generate)
                conf_q = self._confidences_for(inputs, generated_ids)
                generated_text = self._florence_processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
                
                result = self._florence_processor.post_process_generation(
                    generated_text, 
                    task=task_prompt, 
                    image_size=(w, h)
                )
                
                grounding_data = result.get(task_prompt, {})
                bboxes = grounding_data.get("bboxes", [])
                labels = grounding_data.get("labels", [])
                
                for i, (box, label) in enumerate(zip(bboxes, labels)):
                    boxes_out.append([float(box[0]), float(box[1]), float(box[2]), float(box[3])])
                    labels_out.append(label if label else q)
                    scores_out.append(_pick_confidence(conf_q, i))
            except Exception as exc:
                logger.error("Phrase grounding query=%s failed: %s", q, exc)

        # ── 3. Apply NMS to merge and deduplicate boxes ───────────────────────
        boxes_out, labels_out, scores_out = _apply_nms(boxes_out, labels_out, scores_out, iou_threshold=0.60)
        
        return {"boxes": boxes_out, "labels": labels_out, "scores": scores_out}
    # ------------------------------------------------------------------
    # Smart mock
    # ------------------------------------------------------------------

    def _smart_mock(self, image: np.ndarray, prompt: str) -> dict[str, Any]:
        logger.warning("Using mock inference — no model loaded")
        labels = [p.strip() for p in prompt.split(",") if p.strip()][:2] or ["object"]
        h, w = (image.shape[:2] if image.ndim >= 2 else (480, 640))
        regions = [
            [w * 0.15, h * 0.20, w * 0.45, h * 0.55],
            [w * 0.55, h * 0.20, w * 0.85, h * 0.55],
        ]
        boxes, lbls, scores = [], [], []
        for i, label in enumerate(labels):
            boxes.append([float(v) for v in regions[i % len(regions)]])
            lbls.append(label)
            scores.append(round(0.82 - i * 0.07, 2))
        return {"boxes": boxes, "labels": lbls, "scores": scores}

    # ------------------------------------------------------------------
    # Legacy interfaces
    # ------------------------------------------------------------------

    async def infer_from_bytes(self, image_bytes: bytes, prompt: str) -> dict[str, Any]:
        if not _PIL:
            return {"boxes": [], "labels": [], "scores": [], "latency_ms": 0.0}
        pil = PILImage.open(io.BytesIO(image_bytes)).convert("RGB")
        return await self.infer(np.array(pil), prompt)

    def predict(self, image_bytes: bytes, prompt: str) -> dict[str, Any]:
        """Sync interface kept for Celery task compatibility."""
        if not _PIL:
            return {"detections": [], "latency_ms": 0.0}
        pil = PILImage.open(io.BytesIO(image_bytes)).convert("RGB")
        img_rgb = np.array(pil)

        if not self._loaded:
            self._load_best_model()
            self._loaded = True

        loop = asyncio.get_event_loop()
        if loop.is_running():
            result = self._smart_mock(img_rgb, prompt)
        else:
            result = loop.run_until_complete(self.infer(img_rgb, prompt))

        detections = [
            {"label": lbl, "confidence": sc, "bbox": box}
            for lbl, sc, box in zip(result["labels"], result["scores"], result["boxes"])
        ]
        return {"detections": detections, "latency_ms": 0.0, "model_id": self._model_id}

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def is_loaded(self) -> bool:
        return self._loaded

    def get_device(self) -> str:
        return self._device

    def get_stats(self) -> dict[str, Any]:
        return {
            "loaded": self._loaded,
            "device": self._device,
            "model_type": self._model_type,
            "model_id": self._model_id,
            "confidence_threshold": self._confidence_threshold,
            "open_vocabulary": True,
        }
