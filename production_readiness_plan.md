# ArgusLens Production Readiness & Risk Analysis

## 1. Mevcut Sistem Analizi
Önceki fazda gerçek model ağırlıklarına ve inference pipeline'larına geçiş sağlandı. Ancak sistem şu anda "Tekil Düğüm (Single-Node)" mimarisiyle çalışmaktadır. 
- FastApi ve Inference işlemleri aynı süreci veya aynı makineyi paylaşıyor.
- GPU VRAM tahsisi (allocation) manuel çöp toplama (garbage collection) mantığına dayanıyor.
- Kuyruklama (Queue) statik ve distributed load balancer'dan yoksun.
- Loglama standart Python log modülüyle konsola yönlendiriliyor.

## 2. Riskler ve Zafiyetler
- **GPU Race Conditions & OOM:** Eş zamanlı gelen 100+ WebSocket isteği, aynı GPU memory alanında yarışa girip (race condition) Out-Of-Memory hatasına yol açarak backend'i tamamen çökertebilir.
- **Single Point of Failure (SPOF):** Tek bir node/worker arızalandığında tüm inference süreci durur. Failover mekanizması yoktur.
- **Memory Leak (Bellek Sızıntısı):** Server restart anında aktif olan CUDA buffer'ları veya açık WebSocket socket'leri memory leak'e neden olur.
- **Monitoring Eksikliği:** Canlı ortamda GPU sıcaklığı, network darboğazı ve model gecikmeleri proaktif şekilde izlenememektedir.

## 3. Bottleneck (Darboğaz) Analizi
- **Network I/O vs GPU Compute:** WebSocket'ten gelen frame'ler GPU'nun işleme hızından daha hızlıysa (client 60fps atıyor, GPU 15fps işliyorsa), backpressure oluşur ve RAM saniyeler içinde dolar.
- **Synchronous Locking:** Inference anında modeller aynı kaynağı beklerse, async framework'ün bir anlamı kalmaz (thread starvation).

## 4. Çözüm ve Mimari Geçiş Planı
**Faz 3 Hedefleri:**
- `/distributed`: Worker registry ve Healthcheck üzerinden Round-Robin/Least-Loaded mantığında dağıtılmış yük dengeleme.
- `/orchestration`: Semaphore tabanlı async VRAM kilitleme (GPU Lock) ve concurrency limitleri.
- `/monitoring`: Prometheus Histograms ve JSON Structured Logging (Correlation ID).
- `/training`: Resumable Temporal Transformer antrenman mekanizması.

Bu analiz ışığında, gerçek production-ready altyapıya geçiş implementasyonu başlatılmıştır.
