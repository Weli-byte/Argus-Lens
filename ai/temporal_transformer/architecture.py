import torch
import torch.nn as nn
import math

class PositionalEncoding(nn.Module):
    def __init__(self, d_model: int, max_len: int = 5000):
        super().__init__()
        position = torch.arange(max_len).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2) * (-math.log(10000.0) / d_model))
        pe = torch.zeros(max_len, 1, d_model)
        pe[:, 0, 0::2] = torch.sin(position * div_term)
        pe[:, 0, 1::2] = torch.cos(position * div_term)
        self.register_buffer('pe', pe)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Tensor, shape [seq_len, batch_size, embedding_dim]
        """
        x = x + self.pe[:x.size(0)]
        return x

class TemporalTransformer(nn.Module):
    """
    Real Transformer Encoder Architecture for temporal analysis.
    """
    def __init__(self, feature_dim: int, d_model: int = 64, nhead: int = 4, 
                 num_layers: int = 3, dropout: float = 0.1):
        super().__init__()
        self.model_type = 'Transformer'
        self.feature_embedding = nn.Linear(feature_dim, d_model)
        self.pos_encoder = PositionalEncoding(d_model)
        
        encoder_layers = nn.TransformerEncoderLayer(d_model, nhead, dim_feedforward=d_model*4, dropout=dropout)
        self.transformer_encoder = nn.TransformerEncoder(encoder_layers, num_layers)
        
        self.d_model = d_model
        
        # Output heads
        self.risk_head = nn.Sequential(
            nn.Linear(d_model, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid() # Risk score between 0 and 1
        )
        
        self.anomaly_head = nn.Sequential(
            nn.Linear(d_model, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid() # Anomaly probability
        )
        
        self.trend_head = nn.Sequential(
            nn.Linear(d_model, 16),
            nn.ReLU(),
            nn.Linear(16, 3) # 3 classes: up, down, stable
        )

    def forward(self, src: torch.Tensor, src_mask: torch.Tensor = None) -> dict:
        """
        Args:
            src: Tensor, shape [seq_len, batch_size, feature_dim]
        """
        src = self.feature_embedding(src) * math.sqrt(self.d_model)
        src = self.pos_encoder(src)
        output = self.transformer_encoder(src, src_mask)
        
        # Use the last sequence output for prediction
        last_out = output[-1, :, :]
        
        risk_score = self.risk_head(last_out)
        anomaly_prob = self.anomaly_head(last_out)
        trend_logits = self.trend_head(last_out)
        
        return {
            "risk_score": risk_score,
            "anomaly_prob": anomaly_prob,
            "trend_logits": trend_logits
        }
