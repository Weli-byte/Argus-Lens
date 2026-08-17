import torch
import numpy as np
from typing import Optional
from monitoring.log_pipeline import logger

class EarlyStopping:
    """
    Prevents model overfitting by halting training when validation loss stops improving.
    """
    def __init__(self, patience: int = 5, min_delta: float = 0.001):
        self.patience = patience
        self.min_delta = min_delta
        self.counter = 0
        self.best_loss = None
        self.early_stop = False

    def __call__(self, val_loss: float) -> bool:
        if self.best_loss is None:
            self.best_loss = val_loss
        elif val_loss > self.best_loss - self.min_delta:
            self.counter += 1
            logger.info(f"EarlyStopping counter: {self.counter} out of {self.patience}")
            if self.counter >= self.patience:
                self.early_stop = True
                logger.warning("Early stopping triggered. Training halted.")
        else:
            self.best_loss = val_loss
            self.counter = 0
            
        return self.early_stop
