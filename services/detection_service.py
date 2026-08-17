from sqlalchemy.ext.asyncio import AsyncSession
from models.domain import Detection
from typing import List

class DetectionService:
    @staticmethod
    async def get_all_detections(db: AsyncSession) -> List[Detection]:
        # Implementation would go here
        return []

    @staticmethod
    async def create_detection(db: AsyncSession, data: dict) -> Detection:
        # Implementation would go here
        detection = Detection(**data)
        db.add(detection)
        await db.commit()
        await db.refresh(detection)
        return detection
