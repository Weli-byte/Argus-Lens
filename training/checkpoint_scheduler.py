import os
import torch
from typing import Dict, Any
from monitoring.log_pipeline import logger

class CheckpointScheduler:
    """
    Manages safe checkpointing of model weights and optimizer states.
    Allows for resumable training and rollback support.
    """
    def __init__(self, checkpoint_dir: str = "checkpoints/temporal"):
        self.checkpoint_dir = checkpoint_dir
        os.makedirs(self.checkpoint_dir, exist_ok=True)

    def save(self, model: torch.nn.Module, optimizer: torch.optim.Optimizer, 
             epoch: int, loss: float, is_best: bool = False):
        """Saves current state and updates the 'best' model if applicable."""
        state = {
            'epoch': epoch,
            'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(),
            'loss': loss,
        }
        
        filepath = os.path.join(self.checkpoint_dir, f"checkpoint_epoch_{epoch}.pt")
        torch.save(state, filepath)
        logger.info(f"Checkpoint saved: {filepath}")
        
        if is_best:
            best_filepath = os.path.join(self.checkpoint_dir, "best_model.pt")
            torch.save(state, best_filepath)
            logger.info(f"New best model saved: {best_filepath}")

    def load(self, model: torch.nn.Module, optimizer: torch.optim.Optimizer, 
             checkpoint_path: str) -> int:
        """Loads weights to resume training or for inference."""
        if not os.path.exists(checkpoint_path):
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
            
        checkpoint = torch.load(checkpoint_path)
        model.load_state_dict(checkpoint['model_state_dict'])
        optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        
        logger.info(f"Resumed from checkpoint: {checkpoint_path} at epoch {checkpoint['epoch']}")
        return checkpoint['epoch']
