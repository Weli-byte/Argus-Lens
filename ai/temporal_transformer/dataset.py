import torch
from torch.utils.data import Dataset
import numpy as np
from typing import List, Tuple

class TemporalDataset(Dataset):
    """
    Dataset loader for time-series data handling.
    Features: heart_rate, eye_pressure, blink_frequency, fatigue_score, focus_score, neural_latency
    """
    def __init__(self, data: np.ndarray, labels: dict, seq_length: int = 30):
        """
        data shape: (num_samples, seq_length, feature_dim)
        labels: dict of risk_scores, anomalies, trends arrays
        """
        self.data = torch.FloatTensor(data)
        self.risk_labels = torch.FloatTensor(labels['risk'])
        self.anomaly_labels = torch.FloatTensor(labels['anomaly'])
        self.trend_labels = torch.LongTensor(labels['trend'])
        self.seq_length = seq_length

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, dict]:
        # Switch from (batch, seq, feature) to (seq, batch, feature) for PyTorch Transformer
        x = self.data[idx]
        y = {
            "risk": self.risk_labels[idx],
            "anomaly": self.anomaly_labels[idx],
            "trend": self.trend_labels[idx]
        }
        return x, y
