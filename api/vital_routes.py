import logging
import asyncio
from typing import Dict, Any, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
from pydantic import BaseModel

from ai.vital_engine import PhysiologicalSimulator, NEWS2Calculator, MedicalReportGenerator
from ai.temporal_transformer.model import TemporalTransformerModel
from streaming.websocket import ConnectionManager

logger = logging.getLogger(__name__)

router = APIRouter()

# Global Singletons/State for Vitals
simulator = PhysiologicalSimulator()
report_generator = MedicalReportGenerator()
transformer = TemporalTransformerModel(seq_length=30, feature_dim=9)

vital_stream_manager = ConnectionManager()
vitals_history: List[Dict[str, Any]] = []
history_lock = asyncio.Lock()

# Sliding window for Temporal Transformer
vitals_sliding_window: List[List[float]] = []

class ReportRequest(BaseModel):
    vitals: Dict[str, Any]
    news2: Dict[str, Any]

class ReportResponse(BaseModel):
    report: str
    recommendations: str
    model: str

# ---------------------------------------------------------------------------
# Background Task: Vital Sign Broadcaster
# ---------------------------------------------------------------------------
async def start_vital_broadcaster():
    """
    Simulates vital signs at 1Hz, runs NEWS2 + Temporal Transformer, and broadcasts.
    """
    logger.info("Starting background vital sign simulator and broadcaster...")
    global vitals_sliding_window, vitals_history
    
    while True:
        try:
            # 1. Generate new vitals
            v_data = simulator.generate_vitals()
            
            # 2. Calculate NEWS2 score
            n_data = NEWS2Calculator.calculate(
                heart_rate=v_data["heart_rate"],
                systolic_bp=v_data["systolic_bp"],
                spo2=v_data["spo2"],
                temp=v_data["temperature"],
                resp_rate=v_data["respiratory_rate"],
                alert=True
            )
            
            # 3. Add to sliding window for Transformer inference
            # Feature order: HR, SBP, DBP, SpO2, Temp, RR, IOP, Glucose, Cortisol
            feat_vector = [
                v_data["heart_rate"],
                v_data["systolic_bp"],
                v_data["diastolic_bp"],
                v_data["spo2"],
                v_data["temperature"],
                v_data["respiratory_rate"],
                v_data["eye_pressure"],
                v_data["tear_glucose"],
                v_data["stress_level"]
            ]
            vitals_sliding_window.append(feat_vector)
            if len(vitals_sliding_window) > 30:
                vitals_sliding_window.pop(0)
                
            # 4. Run PyTorch Temporal Transformer if we have enough sequence history
            if len(vitals_sliding_window) >= 10:
                analysis = transformer.analyze_sequence(vitals_sliding_window)
            else:
                analysis = {
                    "risk_score": 0.05,
                    "anomaly_probability": 0.02,
                    "trend_direction": "stable"
                }
                
            # 5. Package message
            payload = {
                "vitals": v_data,
                "news2": n_data,
                "analysis": analysis,
                "timestamp": v_data["timestamp"]
            }
            
            # 6. Save to history (limit to 100 items)
            async with history_lock:
                vitals_history.append(payload)
                if len(vitals_history) > 100:
                    vitals_history.pop(0)
                    
            # 7. Broadcast to all active WebSocket connections
            await vital_stream_manager.broadcast_json(payload)
            
        except Exception as e:
            logger.error("Error in vital broadcaster loop: %s", e)
            
        await asyncio.sleep(1.0)

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/vitals/history", response_model=List[Dict[str, Any]])
async def get_vitals_history():
    """
    Returns the last 100 vital sign telemetry records for graph pre-population.
    """
    async with history_lock:
        return list(vitals_history)

@router.post("/vitals/report", response_model=ReportResponse)
async def generate_vital_report(request: ReportRequest):
    """
    Generates a detailed AI clinical report and recommendation list using GPT-4o.
    """
    try:
        res = await report_generator.generate_report(request.vitals, request.news2)
        return ReportResponse(
            report=res["report"],
            recommendations=res["recommendations"],
            model=res["model"]
        )
    except Exception as e:
        logger.error("Failed to generate AI report: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

@router.websocket("/vitals/stream")
async def vitals_websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time vital signs stream.
    """
    await vital_stream_manager.connect(websocket)
    try:
        # Loop to keep connection alive
        while True:
            # We only receive ping or heartbeats from client
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        vital_stream_manager.disconnect(websocket)
    except Exception as e:
        logger.error("Vital WS Error: %s", e)
        vital_stream_manager.disconnect(websocket)
