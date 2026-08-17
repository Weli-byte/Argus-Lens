import torch
import os
from monitoring.log_pipeline import logger

class ONNXExporter:
    """
    Preparation for TensorRT and ONNX Runtime optimization.
    Exports PyTorch models to ONNX format.
    """
    def __init__(self, export_dir: str = "models/onnx"):
        self.export_dir = export_dir
        os.makedirs(self.export_dir, exist_ok=True)

    def export_temporal_transformer(self, pytorch_model: torch.nn.Module, 
                                    seq_len: int = 30, feature_dim: int = 6):
        """Exports the Temporal Transformer to ONNX."""
        
        pytorch_model.eval()
        
        # Create dummy input that matches the shape (seq_len, batch_size, feature_dim)
        dummy_input = torch.randn(seq_len, 1, feature_dim)
        
        export_path = os.path.join(self.export_dir, "temporal_transformer.onnx")
        
        try:
            logger.info(f"Exporting model to {export_path}...")
            
            torch.onnx.export(
                pytorch_model,               # model being run
                dummy_input,                 # model input
                export_path,                 # where to save the model 
                export_params=True,          # store the trained parameter weights inside the model file
                opset_version=14,            # the ONNX version to export the model to
                do_constant_folding=True,    # whether to execute constant folding for optimization
                input_names = ['input_sequence'],   # the model's input names
                output_names = ['risk_score', 'anomaly_prob', 'trend_logits'], # the model's output names
                dynamic_axes={'input_sequence' : {1 : 'batch_size'},    # variable length axes
                              'risk_score' : {0 : 'batch_size'},
                              'anomaly_prob': {0 : 'batch_size'},
                              'trend_logits': {0 : 'batch_size'}}
            )
            logger.info("ONNX Export successful! Ready for TensorRT/ONNXRuntime inference.")
        except Exception as e:
            logger.error(f"ONNX Export failed: {e}")
