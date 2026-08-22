# ArgusLens — Sinematik Landing

Sanat yönü **"Optik Enstrüman"**. Kök rota (`/`) artık `/login`'e yönlenmiyor;
beş sahnelik scroll anlatısı olan bir landing sayfası.

---

## 1. Seçilen yön ve gerekçesi

**Tez:** ArgusLens bir dashboard değil, bir optik alet. Kullanıcı ekrana bakmıyor,
bir merceğin *içinden* bakıyor. Görsel dil bu yüzden ekran değil cam: derinlik,
odak kayması, kaplama parlaması, vinyet.

Üç yön önerildi (Optik Enstrüman / Klinik Vitrin / Gece Ameliyathanesi).
**Optik Enstrüman** seçildi çünkü:

- `CLAUDE.md` tek accent rengi cyan `#00D4FF` olarak sabitliyor. Bu, AI ürünlerinin
  en jenerik paleti. Yön A bu rengi **atmıyor**, ona fiziksel gerekçe veriyor:
  cyan, anti-reflektif mercek kaplamasının gerçek yansıma rengidir. Marka rengi
  "teknoloji mavisi" olmaktan çıkıp **camın kendi rengi** oluyor.
- Hareket dili "odak kaydırma" olarak tanımlanınca `fade-in-up` yapısal olarak
  imkânsız hâle geliyor (reveal primitifi `blur + scale`, `translateY` içermiyor).
- Klinik Vitrin (açık zemin) mevcut karanlık konsolla kopuk kalırdı;
  Gece Ameliyathanesi'nin gerilim tonu sağlık ürününde güveni zedelerdi.

## 2. Tipografi gerekçesi

| Rol | Font | Kesim | Neden |
|---|---|---|---|
| Display | **Bricolage Grotesque** | 200 + 800 | Tek ailede aşırı ağırlık kontrastı. Başlıklarda `GÖZ`(800) ve `artık`(200) yan yana. Editoryal-endüstriyel karakter. |
| Gövde | **Instrument Sans** | 400 | Nötr ama Inter değil. Adı da yöne oturuyor. |
| Manifesto | **Instrument Serif** italik | 400 | Sayfada **bir kez** kullanılır. Sinematik ara başlık. |
| Ölçüm | **Martian Mono** | 300/400 | Geniş, teknik, tabular-nums. FPS/güven%/vital için. |

Dördü de `next/font/google` ile **self-hosted** — dış istek yok.
`latin-ext` alt kümesi zorunlu: `ş ğ ı İ` karakterleri orada.

**Yasaklılara uyum:** Inter, Roboto, Arial, Helvetica, Space Grotesk, Poppins
kullanılmadı. Mor→mavi gradyan yok. Glassmorphism blur kart yok
(`.plate` = 2px yarıçaplı gravür plakası). Düz `#fff`/`#f9fafb` yok.
Tek tip border-radius yok (plaka 2px / hücre 4px / namlu 18px asimetrik /
diyafram tam daire). Emoji ikon yok.

## 3. Palet gerekçesi (OKLCH)

Zemin **siyah değil**: `oklch(0.14 0.014 172)` — grafit-zeytin, kaplamanın
yansıttığı ton. Başlıklar soğuk slate değil **kemik-beyaz**
`oklch(0.93 0.018 85)`. Jenerikliği en çok kıran iki karar bunlar.

```
--surface-ground  oklch(0.14 0.014 172)   grafit-zeytin
--ink-title       oklch(0.93 0.018 85)    kemik, sıcak beyaz
--measure         oklch(0.80 0.128 214)   = #00D4FF, YALNIZ ölçümde
--coating         oklch(0.55 0.140 300)   AR kaplama hayaleti, nadir/specular
--state-alert     oklch(0.78 0.160 70)
--state-critical  oklch(0.62 0.190 25)
```

Cyan disiplini: `.t-measure`, `.cell`, `--edge-live` ve 3D kenar parlaması
dışında hiçbir yerde kullanılmıyor. Dekorda cyan yok.

## 4. Token mimarisi

Tek dosya: `src/app/tokens.css`, üç katman.

1. **Primitive** (`--p-*`) — ham değerler, bileşenler okumaz.
   - Boşluk **Fibonacci**: 4 / 8 / 13 / 21 / 34 / 55 / 89 / 144 / 233 px.
     Lineer 4-8 ızgarası değil; aletin kadran taksimatı.
   - Tipografi: taban 17px, oran 1.333.
2. **Semantic** — `--surface-*`, `--ink-*`, `--edge-*`, `--measure*`.
   Bileşenler **sadece** bu katmanı okur. Koyu ve açık tema burada tanımlı
   (`:root[data-theme="light"]` = "gün ışığı laboratuvarı").
3. **Component** — `--plate-*`, `--barrel-*`, `--cell-*`, `--btn-*`, `--hud-*`.

JSX ve CSS içinde hardcode renk/boşluk/yarıçap sayısı yok.

## 5. Hareket dili

Tek reveal primitifi, `globals.css`:

```css
[data-reveal]          { opacity:0; filter:blur(14px); transform:scale(1.035); }
[data-reveal].in-focus { opacity:1; filter:blur(0);    transform:none; }
```

Yani hiçbir şey aşağıdan yukarı **kaymaz** — odağa **gelir**.

Üç varyant:

- **varsayılan** — IntersectionObserver `.in-focus` ekler (ekran altı içerik).
- **`iris`** — diyafram kanadı gibi `clip-path` ile merkezden açılır.
  Gözlemci eşiği bu yüzden `0.01` olmak zorunda: `clip-path` öğenin kesişim
  alanını %8'e düşürüyor, `0.2` eşiği hiç dolmuyordu (videolar hiç açılmadı).
- **`boot`** — ilk ekran. Saf CSS `@keyframes focusIn`, JS beklemez.
  Bkz. bölüm 7, LCP düzeltmesi 4.

Scroll koreografisi (`SceneChoreography.tsx`), tek pin'li zaman çizelgesi:

| Sahne | Ne anlatıyor | Mekanizma |
|---|---|---|
| 01 GÖZ | göz artık bir arayüz | `pin` + `scrub` → mercek yığını patlatılmış optik diyagrama açılır, kamera içeri girer, metin bulanıklaşarak çıkar, hero erir |
| 02 TARAMA | optik hat, 60 fps | görüntü `scale 1.06 → 1` ile odağa gelir |
| 03 TESPİT | her nesne güven oranıyla | iris reveal + ölçüm satırları |
| 04 YORUM | ham piksel değil klinik okuma | ölçüm listesi görüntüden geride kalır (`yPercent -14`) — okuma gecikmesi |
| 05 AKSİYON | eşik aşıldığında | diyafram + konsola devir |

`snap`: yalnız `pointer: fine` cihazlarda ve yalnız `#anlati` bloğunda.
Dokunmatikte snap kullanıcıyla kavga eder, kapalı.

Mikro-etkileşimler: `FocusReticle` (imleç vizördeki odak noktası olur,
etkileşimli öğe üzerinde halka kilitlenir), `.plate` hover gravür işareti,
`--streak-y` ile scroll boyunca inen anamorfik çizgi.

## 6. 3D katmanı

`LensScene.tsx` — **dönen küp değil**: üç asferik cam eleman, namlu içinde.
Ürünün kendisi.

- Geometri **prosedürel** (`LatheGeometry` + bikonveks profil) → GLTF yok, ağ isteği yok.
- Materyal: özel shader. Ekran uzayı sahte kırılma + **kromatik dispersiyon**
  (R/G/B üç farklı kaymadan örneklenir — gerçek camın yaptığı şey).
- Doku: hero videosunun **kendi `<video>` elementi** `VideoTexture` olarak
  paylaşılır → ikinci indirme yok.
- Işık yok, gölge yok, post-process yok.

**Ölçülen bütçe:**

| Hedef | Ölçüm |
|---|---|
| 3D bundle < 300 KB gzip | **227 KB gzip** (852 KB ham), tembel parça |
| drawcall < 100 | **5 / kare** |
| < 60 fps düşmeyecek | **124 fps**, 0 uzun kare (1x CPU, scroll altında) |

**Düşüş yolları:** `prefers-reduced-motion: reduce`, ≤860px genişlik veya
WebGL yoksa canvas hiç yüklenmez; yerine statik patlatılmış optik diyagram
(iç içe diyafram halkaları) gösterilir.
`<canvas>` viewport'a girmeden **ve** sayfa `load` olmadan init edilmez.

## 7. Ölçülen Core Web Vitals

`next build` + `next start`, Chrome DevTools, **Slow 4G + 4x CPU throttling**:

| Metrik | Eşik | Ölçüm |
|---|---|---|
| **LCP** | < 2.5 s | **1.12 s** (LCP öğesi: hero başlığı) |
| **FCP** | — | **1.13 s** — LCP ile aynı kare |
| **CLS** | < 0.1 | **0.00 – 0.001** |
| Scroll FPS (1x CPU) | ≥ 60 | **124**, 0 uzun kare |
| WebGL drawcall | < 100 | **5 / kare** |
| Konsol hatası | 0 | **0** |

### LCP için yapılan dört düzeltme (hepsi ölçümle doğrulandı)

1. **Hero videosu oynatması `load` sonrasına ertelendi.** İlk ekranda olduğu
   için IntersectionObserver anında tetikleniyor, ~2.5 MB indirme LCP'nin
   önüne geçiyordu. Yavaş 4G'de FCP 2.36 s → 0.92 s.
2. **3D sahne `load` + `requestIdleCallback` sonrasına ertelendi.**
   227 KB'lık three.js parçası render'ı 1.1 s geciktiriyordu.
3. **Poster preload'u `ReactDOM.preload` ile sunucu HTML'ine yazıldı.**
   JSX içindeki `<link rel="preload">` yalnızca istemcide hoist ediliyordu.
   Ayrıca Martian Mono'nun font preload'u kapatıldı — posterle bant genişliği
   yarışıyordu.
4. **İlk ekranın reveal'ı JS'ten koparıldı — en büyük kazanç.**
   `[data-reveal]` öğeleri `opacity: 0` başlıyor ve görünürlüğü
   IntersectionObserver'a bağlı. Hero başlığı için bu, boyamayı paket
   indirme + parse süresinin arkasına kilitliyordu: **LCP 2.80 s, tamamı
   render gecikmesi.** İlk ekran öğeleri saf CSS animasyonu kullanan
   `data-reveal="boot"` varyantına geçirildi (aynı odak-kaydırma hareketi,
   `@keyframes focusIn`). Sonuç: **LCP 2.80 s → 1.12 s** ve FCP ile aynı
   kareye indi. Ekran altı öğeler gözlemciyi kullanmaya devam ediyor.

Ekran altı posterler de tembel: yalnız hero'da `poster` özniteliği var,
diğerleri viewport'a ~400px kala JS ile atanır. Peşin yük 345 KB → 26 KB.

## 8. Erişilebilirlik (WCAG 2.2 AA)

Ölçülen kontrast oranları (zemin `#040b08`):

| Öğe | Boyut/ağırlık | Oran | Gerekli | Sonuç |
|---|---|---|---|---|
| H1 | 112px / 800 | 16.14 | 3.0 | ✓ |
| Gövde | 17px / 400 | 11.43 | 4.5 | ✓ |
| Kadran etiketi | 10px / 300 | 6.91 | 4.5 | ✓ |
| Ölçüm (cyan) | 11.5px / 400 | 11.03 | 4.5 | ✓ |
| İnce başlık | 112px / 200 | 6.91 | 3.0 | ✓ |

Hero metni video üzerinde durduğu için yatay + dikey **scrim** eklendi
(`.grade-optic::before`); videonun en parlak karesinde bile metin kolonu
karanlık kalır.

Diğer denetimler:

- `lang="tr"` → CSS `text-transform: uppercase` Türkçe kurallarına uyuyor
  (`gir` → `GİR`, `GIR` değil).
- Atlama bağlantısı ilk odaklanabilir öğe.
- 14 odaklanabilir öğe, mantıklı sıra; `:focus-visible` 2px cyan halka + offset.
- `<video>` öğeleri `tabIndex={-1}`, her birinin `aria-label`'ı ve görsel
  gizli açıklaması var; kontroller kapalı, ses yok (`muted`).
- 1 adet `h1`, 6 adet `h2`; künye gerçek `<table>` + `<caption>`.
- **`prefers-reduced-motion: reduce` doğrulandı:** 36/36 reveal anında görünür,
  3D canvas hiç yüklenmiyor, nişangâh kapalı, Lenis kapalı, 0 video oynuyor,
  5/5 poster basılı, tüm içerik okunur.
- 3D ve video olmadan sayfa tam okunur ve CTA'lar çalışır.

## 9. Bilinen sınırlar

1. **Videolar 1280×720, 4K değil.** Kaynak klipler bu çözünürlükte üretilmiş.
   4K monitörde tam kaplama hero yumuşak görünür; `.barrel` halation, vinyet
   ve grade bunu kasıtlı bir stil hâline getiriyor. Gerçek 4K isteniyorsa
   klipler upscale edilmeli.
2. **WebM yok — yalnız MP4.** `ffmpeg` sistemde yok ve ağ kısıtlı olduğu için
   (`winget` kaynak güncellemesi başarısız) kurulamadı. Tüm hedef tarayıcılar
   MP4/H.264 destekliyor, işlevsel kayıp yok. `ffmpeg` erişilebilir olunca:
   ```bash
   for f in 01-eye 02-scan 03-detect 04-read 05-act; do
     ffmpeg -i public/video/$f.mp4 -c:v libvpx-vp9 -crf 34 -b:v 0 -an \
       public/video/$f.webm
   done
   ```
   sonra `SceneVideo.tsx` içindeki `<source>` listesine webm'i MP4'ten önce ekle.
3. **Video dosyaları ~2.5 MB/adet, yeniden sıkıştırılmadı** (aynı `ffmpeg`
   sebebi). Poster kareleri headless Chrome ile üretildi (`canvas.toDataURL`),
   960×540 / q0.42, toplam 168 KB.
4. **Poster kareleri t=1.4 sn'den alındı.** Sabit bir seçim; başka bir kare
   daha temsili görünürse `AT` değerini değiştirip yeniden üretmek gerekir.
5. `LensScene.tsx` içinde `react-hooks/immutability` kuralı dosya düzeyinde
   kapalı. Gerekçe dosyanın başında yazılı: three.js materyali React state'i
   değil, harici bir GPU kaynağı; uniform ataması onu güncellemenin tek yolu.
6. **Fiyatlandırma bölümü yok.** Ürünün kamuya açık fiyatı yok; yerine
   teknik künye tablosu kondu. İstenirse eklenir.
7. `chat/page.tsx:67` içinde derlemeyi bloke eden **mevcut** bir tip hatası
   vardı (`Dict<string, boolean>` — TypeScript'te böyle bir tip yok);
   `Record<string, boolean>` olarak düzeltildi. Bu landing işiyle ilgisiz
   ama olmadan `next build` geçmiyordu.
8. `@react-three/drei` kurulmuş ama kullanılmadığı için kaldırıldı
   (bundle bütçesi). Gerekirse geri eklenebilir.
9. Ölçümler yerel `next start` üzerinde, Chrome DevTools throttling ile
   alındı. Gerçek CDN + HTTP/2 altında farklı olacaktır; sayılar mutlak
   değil, karşılaştırmalı kabul edilmeli. Her düzeltme öncesi/sonrası
   aynı koşulda ölçüldü.
10. Ölçüm alırken sayfanın **başa kaydırılmış** olması şart. Aksi hâlde
   tarayıcı kaydırma konumunu geri yükler ve ekran altındaki bir poster
   LCP öğesi olarak raporlanır (bir kez bu tuzağa düşüldü: 6.8 s "LCP",
   aslında `03-detect.jpg`).

## 10. Dosya haritası

```
src/app/tokens.css                  üç katmanlı token sistemi (TEK kaynak)
src/app/globals.css                 tailwind + tokens + landing primitifleri
src/app/layout.tsx                  4 font, lang="tr", data-theme="dark"
src/app/page.tsx                    sayfa kompozisyonu
src/hooks/useMediaQuery.ts          useSyncExternalStore tabanlı medya sorgusu
src/lib/lens-progress.ts            GSAP → useFrame kanalı (React state yok)
src/components/landing/
  Atmosphere.tsx                    5 sabit atmosfer katmanı (server component)
  SiteNav.tsx  SiteFooter.tsx
  Hero.tsx                          sahne 01
  SceneBlock.tsx                    sahne 02-05 (yeniden kullanılır)
  SceneVideo.tsx                    tembel video + poster + IO oynatma
  HudFrame.tsx                      vizör köşe işaretleri
  SpecSheet.tsx                     teknik künye tablosu
  ClosingCTA.tsx
  SceneChoreography.tsx             GSAP ScrollTrigger + Lenis + reveal IO
  FocusReticle.tsx                  odak nişangâhı imleci
  LensStage.tsx                     3D kapısı (yetenek + görünürlük + idle)
  LensScene.tsx                     R3F sahnesi, mercek yığını shader'ı
public/video/01-eye … 05-act.mp4    5 sahne klibi
public/poster/01-eye … 05-act.jpg   960×540 poster kareleri
```

## 11. Giriş ekranı

Sol panelin zemini artık parçacık alanı + SVG göz değil, **gerçek iris çekimi**
(`01-eye.mp4`). Giriş = iris taraması; görüntü işin kendisini anlatıyor.
Klip landing hero'suyla aynı dosya → tarayıcı önbelleğinden gelir, ek indirme yok.
`SceneVideo` kullanıldığı için tembel yükleme, poster ve
`prefers-reduced-motion` davranışı otomatik geliyor.

İki katmanlı scrim: (1) metin bandını hedefleyen elips, (2) kenar vinyeti.
İlk denemede radyal maske ters yöndeydi — merkezi açık bırakıp kenarları
karartıyordu, metin tam merkezde olduğu için okunmuyordu. Düzeltme sonrası
metin bandında **ölçülen kontrast 13.35:1** (video karesi + grade + scrim
kompozisyonu hesaplanarak).

### PORT UYARISI — "Network Error" sebebi

Backend'in CORS allowlist'i **yalnızca `http://localhost:3001`** origin'ine izin
veriyor. Frontend başka bir portta açılırsa (`:3000`, `:3311` …) tarayıcı
preflight'ı bloklar ve axios bunu **"Network Error"** olarak gösterir —
kimlik bilgileriyle ilgisi yoktur.

Bu yüzden `package.json` içindeki `start` betiği `next start -p 3001` olarak
sabitlendi (`dev` zaten `-p 3001` idi). Backend `main.py` ile **:8090**'da çalışır;
`src/lib/config.ts` oraya bakar.

Doğrulandı: `admin` ile giriş → `/dashboard`, canlı vital akışı geliyor.

## 12. Çalıştırma

```bash
cd frontend
npm install
npm run dev            # :3001
npm run build && npm start
npm run lint
```

Backend (`http://127.0.0.1:8000`) kapalıyken landing tamamen çalışır;
landing hiçbir API veya WebSocket çağrısı yapmaz.
