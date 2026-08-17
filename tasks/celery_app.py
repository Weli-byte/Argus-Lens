import os
from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

celery_app = Celery(
    "arguslens_tasks",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)

@celery_app.task(name="process_video_frame_task")
def process_video_frame_task(frame_data_b64: str, prompt: str):
    """
    Background task to process a video frame through Grounding DINO.
    """
    # Import locally to avoid loading models when celery is just reading the file
    from ai.grounding_dino.inference import GroundingDinoPipeline
    
    pipeline = GroundingDinoPipeline()
    # In reality, frame_data_b64 would be decoded to bytes here
    dummy_bytes = b"dummy"
    results = pipeline.predict(dummy_bytes, prompt)
    return results

@celery_app.task(name="analyze_temporal_data_task")
def analyze_temporal_data_task(sequence: list):
    """
    Background task to process temporal data.
    """
    from ai.temporal_transformer.model import TemporalTransformerModel
    
    model = TemporalTransformerModel()
    results = model.analyze_sequence(sequence)
    return results
