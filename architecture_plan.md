# ArgusLens Enterprise Architecture Refactor Plan

## 1. Mevcut Sistem Analizi
Şu anki mimari temiz bir temel sunsa da tamamen "mock" (sahte) verilerle çalışmaktadır:
- `GroundingDinoPipeline` sadece verilen metni döner, gerçek bir model yüklemez veya bounding box çizmez.
- `TemporalTransformerModel` sadece random(rastgele) risk skorları üretir.
- Gerçek bir GPU yönetimi, batching, veya bellek temizleme sistemi yoktur.
- WebSocket altyapısı temel düzeydedir, backpressure (aşırı yüklenme) veya kare atlama mekanizmaları (frame skipping) içermez.
- Güvenlik (JWT, Rate Limiting), Monitoring (Prometheus), ve Embedding (Vector Search) katmanları eksiktir.

## 2. Eksikler ve Gereksinimler
- **AI Inference:** Gerçek model ağırlıkları (weights), CUDA desteği, half-precision (FP16), Tensor/Torch Compile, gerçek NMS.
- **Orchestration:** İstekleri sıraya alıp (queueing) verimli bir şekilde GPU'ya aktaracak (batching) bir engine.
- **Streaming:** Düşük gecikmeli, JPEG sıkıştırmalı, adaptif FPS destekli WebSocket sistemi.
- **Güvenlik & İzleme:** Grafana/Prometheus metrikleri, detaylı loglama, GPU vRAM takibi, JWT/API Key yetkilendirmesi.
- **Veritabanı:** pgvector entegrasyonu, Alembic migration altyapısı, connection pooling.

## 3. Refactor ve Implementasyon Planı

### Faz 1: Altyapı ve Bağımlılıkların Güncellenmesi
- `requirements.txt` dosyasının `pgvector`, `prometheus-client`, `PyJWT`, `passlib`, `sentence-transformers` vb. ile genişletilmesi.
- Veritabanı modellerinin `pgvector` destekleyecek şekilde güncellenmesi.

### Faz 2: Gerçek AI Modellerinin (Grounding DINO & Temporal Transformer) Kurulumu
- `/ai/grounding_dino/`: HuggingFace `AutoModelForZeroShotObjectDetection`, `AutoProcessor` kullanarak gerçek inference. Cihaz tespiti (CUDA/CPU), batching ve annotation altyapısı.
- `/ai/temporal_transformer/`: PyTorch tabanlı gerçek Transformer Encoder mimarisi, dataset loader, normalization ve forecasting mekanizması.

### Faz 3: Orchestration ve Streaming Katmanları
- `/orchestration/`: `gpu_manager` ve `inference_scheduler` ile kaynak tüketimini kontrol altına alma.
- `/streaming/`: `fps_controller` ve `backpressure` modülleri ile gerçek zamanlı görüntü akışında yaşanacak dar boğazları önleme.

### Faz 4: Güvenlik, Versiyonlama ve İzleme
- `/security/`: JWT ve Role-Based Access Control (RBAC).
- `/monitoring/`: Prometheus metrikleri ve GPU takip sistemi.
- `/models/versioning/`: Checkpoint takip mekanizması.

---
Bu plan doğrultusunda, **Faz 1 ve Faz 2** implementasyonlarına derhal başlanacaktır.
