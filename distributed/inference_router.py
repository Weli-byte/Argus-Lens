import json
import uuid
import asyncio
from monitoring.log_pipeline import logger
from distributed.worker_registry import WorkerRegistry
from tasks.celery_app import celery_app # Assuming we use Celery for distributed routing

class InferenceRouter:
    """
    Routes incoming inference requests to the optimal distributed worker node.
    """
    def __init__(self):
        self.registry = WorkerRegistry()

    async def route_task(self, task_name: str, args: list, kwargs: dict = None) -> str:
        """
        Determines the best worker and routes the Celery task specifically to its queue.
        If no worker is available, falls back to the default queue.
        """
        if kwargs is None:
            kwargs = {}
            
        best_worker = await self.registry.get_least_loaded_worker()
        task_id = str(uuid.uuid4())
        
        if best_worker:
            logger.info(f"Routing task {task_id} to worker {best_worker}")
            # Route to a specific queue named after the worker ID
            celery_app.send_task(
                task_name,
                args=args,
                kwargs=kwargs,
                queue=f"worker_{best_worker}",
                task_id=task_id
            )
        else:
            logger.warning(f"No active workers found! Falling back to default queue for task {task_id}")
            celery_app.send_task(
                task_name,
                args=args,
                kwargs=kwargs,
                task_id=task_id
            )
            
        return task_id
