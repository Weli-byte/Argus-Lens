<div align="center">

# ArgusLens

**Biyonik lens görü platformu — gerçek zamanlı nesne tespiti, göz hastalığı simülasyonu, vital izleme ve klinik AI asistan, tek optik hat üzerinde.**

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-16.2-000000?logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.3%2B-EE4C2C?logo=pytorch&logoColor=white)](https://pytorch.org/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

[Hızlı başlangıç](#hızlı-başlangıç) · [Mimari](#mimari) · [Modeller](#modeller) · [API](#api-referansı) · [Katkı](#katkı)

</div>

---

## ⚠️ Kapsam ve sınırlar — önce bunu okuyun

ArgusLens bir **araştırma ve gösterim** projesidir. Tıbbi cihaz değildir, teşhis aracı değildir ve klinik kullanım için onaylanmamıştır.

Somut olarak:

| Bileşen | Durum |
|---|---|
| Nesne tespiti | **Gerçek.** Florence-2 modeli canlı çalışır, güven oranı modelin kendi olasılığından türetilir. |
| Göz hastalığı görüntüleme | **Gerçek görsel simülasyon.** Kamera görüntüsüne uygulanan optik filtreler; tanı değil, hastalığın *nasıl göründüğünü* anlatan bir eğitim aracı. |
| Vital değerler | **Simüle.** Fizyolojik durum makinesi üretir; bağlı bir sensör yoktur. |
| NEWS2 skoru | **Gerçek klinik ölçek**, standart eşiklerle doğru uygulanmış — ama simüle veri üzerinde çalışır. |
| Temporal Transformer | **Mimari gerçek, ağırlıklar eğitilmemiş.** Ayrıntı için [Modeller](#modeller). |
| Klinik AI asistan | **Gerçek**, OpenAI GPT-4o. Yanıtları teşhis değildir. |

Acil bir durumda 112'yi arayın.

---

## ArgusLens nedir

Biyonik bir kontakt lensin göreceği dünyayı bir tarayıcıda canlandırır. Beş konsol ekranı:

- **Kamera** — canlı kamera görüntüsü üzerinde 22 göz hastalığının görsel simülasyonu, şiddet kadranı ve sağlıklı gözle yan yana karşılaştırma.
- **Nesne Tespiti** — açık sözcük dağarcıklı tespit. "araba, insan, ağaç" yazın; model o nesneleri bulur, kutular ve gerçek güven oranı çizer.
- **Vital Değerler** — nabız, SpO₂, tansiyon, solunum, göz içi basıncı, gözyaşı glikozu ve kortizol; NEWS2 erken uyarı skoru ve anomali indeksi.
- **AI Asistan** — vital telemetriyi RAG ile bağlama katan klinik sohbet.
- **Sağlık Profili** — hasta künyesi, sigorta, acil durum kişisi, kronik hastalık/alerji/ilaç etiketleri, E-Nabız rapor içe aktarımı.

Arayüz **Türkçe ve İngilizce** çalışır; üst çubuktaki `TR / EN` anahtarı tüm ekranları çevirir. Ayrıntı: [`frontend/DIL.md`](frontend/DIL.md).

---

## Hızlı başlangıç

### Gereksinimler

| | Sürüm |
|---|---|
| Python | 3.11+ |
| Node.js | 20+ |
| GPU | İsteğe bağlı. CUDA varsa kullanılır; yoksa CPU'ya düşer. |

### Kurulum

```bash
git clone https://github.com/Weli-byte/Argus-Lens.git
cd Argus-Lens
```

**Arka uç**

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate

pip install -r requirements.txt
python main.py          # http://127.0.0.1:8090
```

İlk çalıştırmada Florence-2 (~0,5 GB) Hugging Face'ten indirilir ve standart HF önbelleğine
(`~/.cache/huggingface`) yazılır. Depodaki `model_cache/florence2_lora/` bundan ayrıdır —
`train.py` ile üretilmiş LoRA adaptörüdür.

**Ön yüz**

```bash
cd frontend
npm install
npm run dev             # http://localhost:3000
```

Arka uç kapalıyken arayüz yine açılır; veri alanları boş kalır.

### Yapılandırma

Kök dizine `.env` oluşturun. **Bu dosya git'e girmez.**

```bash
# Google ile giriş — istemci kimliği (gizli değil, tarayıcıya gönderilir)
GOOGLE_CLIENT_ID=xxxxxxxxx.apps.googleusercontent.com

# Klinik AI asistan. Tanımsızsa asistan demo modunda çalışır.
OPENAI_API_KEY=sk-...

# Apple ile giriş — Apple Developer üyeliği + HTTPS + gerçek alan adı gerekir.
# APPLE_CLIENT_ID=com.example.arguslens

# SMS sağlayıcısı. Tanımsızken OTP kodu yanıtta dev_code olarak döner.
# SMS_PROVIDER_KEY=...
```

> **Güvenlik:** `OPENAI_API_KEY` ve `SMS_PROVIDER_KEY` gerçek sırlardır — paylaşmayın, commit etmeyin. Google istemci kimliği tasarım gereği geneldir. Kurulum adımları: [`GOOGLE-APPLE-KURULUM.md`](GOOGLE-APPLE-KURULUM.md).

---

## Mimari

```
┌──────────────────── Next.js 16 · App Router ─────────────────────┐
│  Kamera · Tespit · Vital · Asistan · Profil    │  TR/EN katmanı   │
└──────────────┬─────────────────────────────────┴──────────────────┘
               │  REST (/api/v1)  +  WebSocket (telemetri)
┌──────────────▼───────────────── FastAPI ──────────────────────────┐
│  api/         REST rotaları — auth, detect, vitals, chat, profile │
│  ai/          Model hattı — Florence-2, Temporal Transformer, GPT │
│  streaming/   WebSocket yayın katmanı                             │
│  core/        Kimlik, OIDC doğrulama, kullanıcı deposu, ayarlar   │
│  orchestration/  GPU sağlık izleme ve iş yürütme                  │
└───────────────────────────────────────────────────────────────────┘
```

### Depo düzeni

| Dizin | İçerik |
|---|---|
| `main.py` | FastAPI giriş noktası (port 8090) |
| `api/` | REST rotaları — `endpoints.py`, `auth.py`, `vital_routes.py`, `chat_routes.py`, `profile_routes.py` |
| `ai/grounding_dino/` | Nesne tespiti hattı (sınıf adı geriye dönük uyumluluk için korunmuş) |
| `ai/temporal_transformer/` | Zaman serisi mimarisi, çıkarım sarmalayıcısı, veri kümesi |
| `ai/vital_engine.py` | NEWS2 hesaplayıcı + fizyolojik vital simülatörü |
| `ai/chat_engine.py` | GPT-4o klinik asistan |
| `core/` | `user_store.py` (PBKDF2), `oidc.py` (JWKS doğrulama), `config.py` |
| `streaming/` | WebSocket yayın ve gecikme denetimi |
| `frontend/` | Next.js 16 + Tailwind v4 arayüz |

### Ön yüz tasarım sistemi

Üç katmanlı token mimarisi (`frontend/src/app/tokens.css`): ilkel `--p-*` → anlamsal → bileşen. OKLCH renk uzayı.

Renk görevleri kesindir:

| Renk | Yalnızca |
|---|---|
| Camgöbeği `#00D4FF` | Ölçülmüş değer |
| Kehribar `#E8A33D` | Durum ve aktif seçim |
| Kemik `#F0E9DC` | Başlık ve birincil eylem |
| Kırmızı `#E5484D` | Gerçek tehlike |

Hareket dili "odak kaydırma" (bulanıklık + ölçek), `translateY` + solma değil. Ayrıntı: [`frontend/LANDING.md`](frontend/LANDING.md).

---

## Modeller

### 1. Florence-2 — nesne tespiti

**Ne:** `microsoft/Florence-2-base` (~230M parametre), Microsoft'un görsel-dil temel modeli. `ai/grounding_dino/inference.py`.

**Nasıl çalışır:** Florence-2 bir **üretici** modeldir — YOLO gibi sabit sınıf listesi ve sınıflandırma başlığı yoktur. Görüntüyü bir görü kodlayıcıdan geçirir, ardından bir metin çözücü ile *token üretir*. Kutu koordinatları da token'dır: görüntü 1000 kutucuğa bölünür ve model `<loc_0>`…`<loc_999>` sözcüklerini yazar.

Tipik çıktı:

```
car<loc_58><loc_274><loc_324><loc_711><loc_401>...person<loc_112>...
```

Yani bir tespit = tam olarak 4 konum token'ı. Hat iki görevi birlikte kullanır:

| Görev | Ne yapar |
|---|---|
| `<OD>` | Yoğun tespit — sahnedeki tüm bilinen nesneleri tek geçişte bulur |
| `<CAPTION_TO_PHRASE_GROUNDING>` | Serbest metin sorgusunu ("kırmızı şemsiye") görüntüde konumlandırır |

Sonuçlar birleştirilir ve **NMS** (IoU 0,60) ile yinelenen kutular ayıklanır.

**Ne işe yarar:** Açık sözcük dağarcığı. COCO'nun 80 sınıfıyla sınırlı değilsiniz; modele daha önce hiç etiket görmediği bir nesneyi tarif edip buldurabilirsiniz. Türkçe sorgular İngilizceye çevrilip modele öyle verilir.

**Güven oranı nereden gelir:** Florence-2 hazır bir "confidence" döndürmez. Oran, modelin kendi token olasılıklarından türetilir:

- Üretilen dizi decoder girdisi olarak modele geri beslenir (öğretmen zorlaması, tek ileri geçiş) ve her adımın tam olasılık dağılımı alınır.
- Her konum token'ında tek olasılık yerine **±2 kutucukluk toplam kütle** ölçülür. Sebep: model bir kenardan emin olduğunda bile olasılık bitişik kutucuklara yayılır. Ölçüm: `<loc_521>` tek başına 0,377 — komşularıyla 0,986. Gerçekten belirsiz kenarlar düşük kalır (`<loc_998>` 0,038 → 0,039), yani ayırt etme gücü korunur.
- Tespitin güveni, o dört konum token'ının geometrik ortalamasıdır.

Etiket token'ı bilerek dışarıda bırakılır: `<OD>` modunda etiket kutu başına yazılmaz (ölçülen bir görselde 32 kutu için yalnızca 6 etiket token'ı vardı) ve o olasılık "sınıf doğru mu" değil "yeni bir sınıfa mı geçiyorum" kararını yansıtır.

> Ölçüm — 24 nesneli sokak fotoğrafı: **24/24 benzersiz oran, %61–%99 aralığı**, çıkarım 2,5 sn.

### 2. Temporal Transformer — zaman serisi analizi

**Ne:** Özel PyTorch encoder. `ai/temporal_transformer/architecture.py`.

```
girdi   (30 adım × 9 özellik)
        └─ doğrusal gömme → d_model 64
        └─ sinüzoidal konum kodlaması
        └─ 3 × TransformerEncoderLayer (4 başlık, FFN 256)
        └─ 3 çıkış başlığı:  risk (sigmoid) · anomali (sigmoid) · trend (3 sınıf)
```

Dokuz özellik: nabız, sistolik/diastolik tansiyon, SpO₂, sıcaklık, solunum hızı, göz içi basıncı, glikoz, kortizol.

**Dürüst durum:** Mimari gerçek ve her istekte gerçek bir ileri geçiş çalışır, **ancak hiçbir yerde eğitilmiş ağırlık yüklenmez** — `TemporalInferencer` `model_path=None` ile kurulur, yani ağırlıklar rastgele başlatılmıştır. Bu yüzden ekranda gördüğünüz risk ve anomali değerleri transformer'dan **gelmez**.

**Değerleri gerçekte ne üretir:** Kural tabanlı bir fizyolojik sapma motoru (`ai/temporal_transformer/model.py`). Her vital için klinik referans aralığından sapma ölçülür —

| Vital | Normal aralık |
|---|---|
| Nabız | 60–100 /dk |
| Sistolik tansiyon | 90–140 mmHg |
| SpO₂ | ≥ %95 (daha ağır ağırlıklandırılır) |
| Sıcaklık | 36,1–37,5 °C |
| Solunum | 12–20 /dk |
| Göz içi basıncı | 10–21 mmHg |
| Glikoz | 70–120 mg/dL |
| Kortizol | 5–20 mcg/dL |

— toplam sapma `0,05 + 0,90 · (1 − e^(−sapma·0,8))` ile anomali olasılığına eşlenir. Trend yönü, kayan pencerede nabız/sıcaklık/tansiyon farkından hesaplanır.

Eğitim iskeleti (`train.py`, `ai/temporal_transformer/dataset.py`) depoda hazır; bir checkpoint eğitilip `TemporalInferencer(model_path=...)` ile yüklendiği anda transformer devreye girer.

### 3. NEWS2 — klinik erken uyarı skoru

**Ne:** İngiltere Kraliyet Hekimler Koleji'nin *National Early Warning Score 2* ölçeği. `ai/vital_engine.py`.

**Nasıl çalışır:** Model değil, standartlaştırılmış bir puanlama tablosudur. Altı parametre (solunum, SpO₂, sistolik tansiyon, nabız, sıcaklık, bilinç düzeyi) her biri 0–3 puan alır, toplam 0–20 arası bir skor verir.

| Skor | Anlam |
|---|---|
| 0–4 | Düşük risk |
| 5–6 | Orta risk — acil değerlendirme |
| 7+ | Yüksek risk / kritik |

**Ne işe yarar:** Hastanelerde hastanın kötüleşmesini erken yakalamak için kullanılır. Uygulaması standarda sadıktır; girdi verisi simüle olduğu için çıktı da gösterim amaçlıdır.

### 4. GPT-4o — klinik asistan

**Ne:** OpenAI `gpt-4o`, `ai/chat_engine.py` üzerinden.

**Nasıl çalışır:** Anlık vital telemetri ve hasta profili sistem istemine bağlam olarak (RAG) enjekte edilir; asistan soruları bu bağlamla yanıtlar. Görüntü yükleme, derin düşünme (CoT) ve canlı web araştırması seçenekleri vardır.

**Ne işe yarar:** Kullanıcının kendi ölçümlerini düz Türkçe/İngilizce sorabilmesi. `OPENAI_API_KEY` yoksa kural tabanlı demo moduna düşer. Yanıtlar teşhis değildir ve arayüz bunu her oturumda belirtir.

### 5. Göz hastalığı simülasyonu

**Ne:** Model değil — canvas filtre hattı, `frontend/src/hooks/useEyeFilter.ts`.

**Nasıl çalışır:** Kamera karesine her hastalığın optik imzasına karşılık gelen CSS/canvas filtreleri uygulanır: miyopide uzak bulanıklık, glokomda tünel maskesi, katarakta sarımsı sisleme, renk körlüğünde SVG renk matrisi, keratokonusta hayalet iz. Şiddet kadranı bulanıklık yarıçapını ve karışım yoğunluğunu ölçekler.

**Ne işe yarar:** 22 hastalığın *nasıl göründüğünü* göstermek — hasta eğitimi ve empati aracı. Tanı koymaz.

> Şiddet kadranı yüzde gösterir, gerçek diyoptri değil.

---

## API referansı

Taban yol: `/api/v1` · Etkileşimli dokümantasyon: `http://127.0.0.1:8090/docs`

### Kimlik

| Yöntem | Yol | Açıklama |
|---|---|---|
| `POST` | `/register` | E-posta veya telefonla kayıt |
| `POST` | `/auth/token` | Kullanıcı adı/parola ile giriş |
| `POST` | `/oauth/google` | Google kimlik token'ı doğrulama (JWKS imza kontrolü) |
| `POST` | `/oauth/apple` | Apple kimlik token'ı doğrulama |
| `POST` | `/otp/request` · `/otp/verify` | Telefon + tek kullanımlık kod |
| `GET` | `/providers` | Hangi sosyal sağlayıcıların yapılandırıldığı |

Parolalar PBKDF2-HMAC-SHA256 ile 200.000 tur hash'lenir. OIDC token'ları PyJWT + `cryptography` ile imza, `exp`, `iat`, `aud`, `iss`, `sub` alanları doğrulanarak kabul edilir; doğrulanmamış e-posta reddedilir.

### Görü ve analiz

| Yöntem | Yol | Açıklama |
|---|---|---|
| `POST` | `/detect` | Nesne tespiti — base64 görüntü + metin sorgusu |
| `GET` | `/detections` | Son tespit kayıtları |
| `GET` | `/vitals/history` | Vital zaman serisi |
| `POST` | `/temporal/analyze` | Dizi üzerinde risk/anomali/trend |
| `POST` | `/vitals/report` · `/generate-report` | GPT-4o hekim raporu |
| `POST` | `/chat/converse` | Klinik asistan |
| `POST` | `/upload-enabiz` | E-Nabız sağlık raporu içe aktarımı |

<details>
<summary><b>Örnek — nesne tespiti</b></summary>

```bash
curl -X POST http://127.0.0.1:8090/api/v1/detect \
  -H "Content-Type: application/json" \
  -d '{
    "image_base64": "<base64>",
    "prompt": "araba, insan, otobüs",
    "language": "tr",
    "confidence_threshold": 0.25
  }'
```

```json
{
  "boxes": [
    { "x1": 412, "y1": 268, "x2": 590, "y2": 372,
      "label": "car", "label_tr": "araba", "score": 0.9890, "color": "#00D4FF" }
  ],
  "latency_ms": 2523.1
}
```

`score` her nesne için ayrı hesaplanır. Eşiğin altında kalan kutular elenir — model bir tespitten emin değilse o kutu gösterilmez.

</details>

---

## Geliştirme

```bash
# Arka uç
python main.py

# Ön yüz
cd frontend
npm run dev        # geliştirme sunucusu, sıcak yeniden yükleme
npm run build      # üretim derlemesi
npm run lint       # ESLint + React Compiler kuralları
```

> `npm start` üretim modunda çalışır ve derlemeyi belleğe alır; kod değişiklikleri ancak `npm run build` + yeniden başlatma sonrası görünür. Geliştirirken `npm run dev` kullanın.

### Docker

```bash
docker compose up --build
```

### Belgeler

| Dosya | İçerik |
|---|---|
| [`frontend/DIL.md`](frontend/DIL.md) | TR/EN dil katmanı — nasıl çalışır, yeni metin nasıl eklenir |
| [`frontend/LANDING.md`](frontend/LANDING.md) | Tasarım sistemi ve hareket dili |
| [`AUTH.md`](AUTH.md) | Kimlik akışları ve güvenlik kararları |
| [`GOOGLE-APPLE-KURULUM.md`](GOOGLE-APPLE-KURULUM.md) | Sosyal giriş kurulumu |
| [`CLAUDE.md`](CLAUDE.md) | Depo çalışma kuralları |

---

## Bilinen sınırlar

- Vital veriler simüledir; bağlı bir donanım sensörü yoktur.
- Temporal Transformer eğitilmemiştir — risk/anomali değerleri kural tabanlı motordan gelir.
- Göz hastalığı şiddeti yüzde gösterir, klinik diyoptri değil.
- Apple ile giriş ücretli Apple Developer üyeliği, HTTPS ve gerçek alan adı gerektirir; `localhost`'ta çalışmaz.
- Tanıtım videoları 1280×720'dir, 4K değil.
- TC kimlik numarası bilerek saklanmaz — uygulamanın hiçbir yerinde doğrulanmıyor, saklanması gereksiz risk olurdu.

---

## Katkı

1. Depoyu çatallayın ve bir dal açın: `git checkout -b ozellik/aciklayici-ad`
2. `npm run lint` ve `npm run build` temiz geçmeli.
3. Arayüz metinleri Türkçe yazılır; İngilizce karşılığı `frontend/src/lib/i18n.tsx` sözlüğüne eklenir.
4. Renk görevlerine uyun — camgöbeği yalnızca ölçülmüş değerlerde.
5. Sırları asla commit etmeyin. `.env` ve `data/users.json` `.gitignore`'dadır.

Ölçülebilir iddialar yazın: "hızlı" değil, "LCP 1,12 sn".

---

## Lisans

[MIT](LICENSE) · © 2026 Veli Parlak
