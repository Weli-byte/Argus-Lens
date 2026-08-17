# ArgusLens

Biyonik lens sağlık platformu: gerçek zamanlı göz kamerası simülasyonu, AI nesne tespiti, vital izleme ve klinik AI asistan. Python/FastAPI backend + Next.js frontend.

## Mimari

```
main.py                 # FastAPI giriş noktası (port 8000)
api/                    # REST rotaları (auth, chat, profile, vitals, detect, v1/*)
ai/                     # Modeller: GroundingDINO, temporal transformer, chat/vital engine
streaming/              # WebSocket yayın katmanı (telemetri, inference)
agents/ orchestration/  # Agent ve GPU orkestrasyon katmanları
frontend/               # Next.js 16 (App Router) + Tailwind v4 — bkz. frontend/CLAUDE.md
```

Frontend `http://127.0.0.1:8000` backend'ine bağlanır (REST + WS). Backend kapalıyken UI açılır; veri alanları boş kalır.

## Komutlar

```bash
# Backend
pip install -r requirements.txt
python main.py                      # FastAPI :8000

# Frontend
cd frontend
npm install
npm run dev                         # Next.js :3000
npm run build && npm run lint
```

## Frontend kuralları (UI Design System)

- **Tek accent renk: cyan `#00D4FF`.** Yeşil/emerald/teal kullanma; kırmızı yalnızca gerçek hata/tehlike durumları için.
- Zemin: `#080B0F`; kartlar `linear-gradient(135deg, #0D1117, #111827)` + `border rgba(0,212,255,0.12-0.15)` + `rounded-2xl`.
- Kart hover: globals'taki `.card-lift` sınıfı (translateY(-4px) + cyan glow). Yeni kartlara bunu ekle.
- Başlıklar: font-weight 800-900, tracking-tight; büyük sayfa başlıkları "BEYAZ + cyan" iki kelime kalıbı.
- Animasyon: framer-motion (sayfa geçişleri layout'ta), CSS keyframe'ler `frontend/src/app/globals.css` içinde (blink, shimmer, ring-pulse, floatDot, scanY, msgIn, charIn, ringDraw, cursorRipple).
- Paylaşılan görsel bileşenler: `frontend/src/components/ui/` — `CountUp`, `ParticleField`, `TiltCard`, `MetricCard`; global: `CustomCursor`, `CommandPalette` (Ctrl+K).
- Metinler Türkçe; teknik terimler (FPS, RTT, Inference) olduğu gibi kalır.

## Sınırlar

- UI görevlerinde **backend'e, WebSocket/API çağrılarına, state yönetimine (zustand store'lar, hook'lar) dokunma** — sadece JSX/Tailwind/animasyon.
- `frontend/CLAUDE.md` → `AGENTS.md`: Next.js sürümü eğitim verisinden farklı olabilir; kod yazmadan önce `node_modules/next/dist/docs/` içindeki ilgili rehberi oku.
- Rotalar `/dashboard/*` altında (kamera=vision, detection, vitals, chat, profile). Kök `(dashboard)/detection` gibi eski rotalar redirect'tir; yeni link ekleme.
