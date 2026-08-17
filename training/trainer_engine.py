import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from typing import Dict
from monitoring.log_pipeline import logger
from training.early_stopping import EarlyStopping
from training.checkpoint_scheduler import CheckpointScheduler

class TrainerEngine:
    """
    Enterprise PyTorch Training Engine for Temporal Transformer.
    Includes early stopping, checkpointing, and metric tracking.
    """
    def __init__(self, model: nn.Module, train_loader: DataLoader, val_loader: DataLoader, 
                 learning_rate: float = 1e-4, epochs: int = 50):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = model.to(self.device)
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.epochs = epochs
        
        self.optimizer = torch.optim.AdamW(self.model.parameters(), lr=learning_rate)
        self.criterion_risk = nn.MSELoss()
        self.criterion_trend = nn.CrossEntropyLoss()
        
        self.early_stopping = EarlyStopping(patience=7)
        self.checkpoint_scheduler = CheckpointScheduler()

    def train_epoch(self) -> float:
        self.model.train()
        total_loss = 0
        
        for batch_idx, (x, y) in enumerate(self.train_loader):
            x = x.to(self.device)
            y_risk = y["risk"].to(self.device)
            y_trend = y["trend"].to(self.device)
            
            self.optimizer.zero_grad()
            outputs = self.model(x)
            
            loss_risk = self.criterion_risk(outputs["risk_score"].squeeze(), y_risk)
            loss_trend = self.criterion_trend(outputs["trend_logits"].squeeze(0), y_trend)
            
            loss = loss_risk + loss_trend
            loss.backward()
            
            # Gradient clipping to prevent exploding gradients
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            
            self.optimizer.step()
            total_loss += loss.item()
            
        return total_loss / len(self.train_loader)

    def validate(self) -> float:
        self.model.eval()
        total_loss = 0
        with torch.no_grad():
            for x, y in self.val_loader:
                x = x.to(self.device)
                y_risk = y["risk"].to(self.device)
                y_trend = y["trend"].to(self.device)
                
                outputs = self.model(x)
                loss_risk = self.criterion_risk(outputs["risk_score"].squeeze(), y_risk)
                loss_trend = self.criterion_trend(outputs["trend_logits"].squeeze(0), y_trend)
                
                total_loss += (loss_risk + loss_trend).item()
                
        return total_loss / len(self.val_loader)

    def run(self):
        logger.info(f"Starting Temporal Training Lifecycle for {self.epochs} epochs on {self.device}")
        
        for epoch in range(1, self.epochs + 1):
            train_loss = self.train_epoch()
            val_loss = self.validate()
            
            logger.info(f"Epoch {epoch}/{self.epochs} | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f}")
            
            # Save checkpoint
            is_best = False
            if self.early_stopping.best_loss is None or val_loss < self.early_stopping.best_loss:
                is_best = True
                
            self.checkpoint_scheduler.save(self.model, self.optimizer, epoch, val_loss, is_best=is_best)
            
            # Check early stopping
            if self.early_stopping(val_loss):
                break
                
        logger.info("Training Lifecycle completed.")
