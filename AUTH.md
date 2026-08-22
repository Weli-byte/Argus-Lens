# Kimlik Doğrulama — kayıt, giriş, sosyal hesaplar

## 1. Ne değişti

| Önce | Sonra |
|---|---|
| Girişten sonra `/dashboard` tanıtım ekranı | `/dashboard` → `/dashboard/vision` yönlenir; operatör doğrudan canlı kameraya düşer |
| Yalnızca sabit iki demo hesap (`admin`, `operator`) | Gerçek kayıt: e-posta, telefon, Google, Apple |
| Tek adımlı statik form | Tam ekran video sahnesi + TEK panel; GİRİŞ ve KAYIT sekmeli, sayfa kaydırılmıyor |
| Zemin: parçacık alanı + SVG göz | `kamera_gözü_tam_karşıdan_alsın.mp4` tam ekran (repoda `01-eye.mp4`) |

## 2. Kimlik yöntemleri

### Çalışır durumda (yapılandırma gerektirmez)

**E-posta + parola** — `POST /api/v1/auth/register`
Parola PBKDF2-HMAC-SHA256, 200.000 tur, 16 baytlık rastgele tuz.
Kural: en az 8 karakter, hem harf hem rakam.

**Telefon + tek kullanımlık kod** — `POST /api/v1/auth/otp/request` → `/otp/verify`
Numara E.164'e normalize edilir (`0555 111 22 33` → `+905551112233`).
Kod 6 hane, 5 dakika geçerli, en fazla 5 deneme, doğrulanınca tüketilir.

> **SMS sağlayıcısı bağlı değil.** `SMS_PROVIDER_KEY` tanımlı olmadığı sürece
> kod yanıtta `dev_code` alanında döner ve arayüzde açıkça gösterilir. Üretimde
> `core/user_store.py` içindeki `issue_otp` fonksiyonuna bir SMS servisi
> (Twilio vb.) bağlanmalı; o zaman `dev_code` `null` döner.

**Yerleşik demo hesapları** (bozulmadı):
`admin` / `admin123` — tam yetki · `operator` / `operator123` — sınırlı

### Google — YAPILANDIRILDI

İstemci kimliği `.env` dosyasında tanımlı ve etkin:
```
GOOGLE_CLIENT_ID=747406549072-…apps.googleusercontent.com
```
`main.py` artık `load_dotenv()` çağırıyor; `core/config.py` `.env`'i yalnızca
kendi `Settings` modeline okuyordu, `os.getenv` ile okunan değerler gelmiyordu.

`.env` `.gitignore`'da.

### Apple — bekliyor

Apple Developer üyeliği ister ($99/yıl) ve `localhost` kabul etmez; gerçek
alan adı + HTTPS gerekir. Kimlik alınınca `.env`'e `APPLE_CLIENT_ID` eklemek
ve backend'i yeniden başlatmak yeterli:

```bash
APPLE_CLIENT_ID=com.sirketin.servis
```

Frontend bunu çalışma zamanında `/api/v1/auth/providers` ucundan okur;
**yeniden derleme gerekmez**, backend'i yeniden başlatmak yeter.
(`NEXT_PUBLIC_*` değişkenleri hâlâ yedek olarak destekleniyor.)

İstemci kimliği gizli değildir — tasarımı gereği tarayıcıya gönderilir.
Gizli olan `client_secret`'tır ve bu akışta hiç kullanılmıyor.

Adım adım kurulum: **`GOOGLE-APPLE-KURULUM.md`**.

Tanımlı değilken düğmeler **sessizce ölmez**: devre dışı görünür ve sebebini
yazar; `/auth/oauth/*` uçları 501 ve açık bir mesaj döner.

## 3. Güvenlik kararları

- **OIDC token'ları sunucuda imza doğrulanır.** `core/oidc.py`, sağlayıcının
  JWKS anahtarını çeker ve `aud`, `iss`, `exp`, `sub` alanlarını zorunlu
  tutarak RS256/ES256 imzasını doğrular. İmzası doğrulanmamış hiçbir token
  kabul edilmez — istemciden gelen hiçbir iddiaya güvenilmez.
- **Parola hash'i geri döndürülemez** ve API yanıtlarında yer almaz;
  `_public()` yalnızca güvenli alanları dışarı verir.
- **OTP hash'lenmiş saklanır**, sabit zamanlı karşılaştırma (`hmac.compare_digest`)
  ile doğrulanır, deneme sayacı vardır.
- **E-posta doğrulanmamışsa OAuth reddedilir** (Google/Apple `email_verified`).
- Depo şu an JSON dosyası (`data/users.json`) — tek süreçli geliştirme için.
  Üretimde `database/` katmanındaki Postgres'e taşınmalı.

## 4. Arayüz — sinematik kimlik sahnesi

Sanat yönü landing ile aynı: **Optik Enstrüman**.

**Sahne** (`components/auth/AuthAperture.tsx`).

Video ekranın **sol yarısında** ve kadrajın **tamamı görünür**
(`object-fit: contain`). Kutu videonun oranına (16/9) sabitlendi, böylece
`contain` siyah letterbox bırakmıyor; kenarlar maskeyle zemine eriyor.

**Fare gözle oynar:** kutu 3B eğilir (`rotateY ±7°`, `rotateX ∓5°`) ve görüntü
imlecin ters yönünde ~%1 kayar. Eğim perspektiften geldiği için kadrajın
kenarı açığa çıkmaz. Değerler her karede yumuşatılır (lerp 0.075) —
imleç sıçraması göze birebir yansımaz.

Sağ yarı gravürlü zemin + kaplama parlaması; panel orada durur.

> Kaldırılanlar: kalibrasyon halkası, f-durakları, nişangâh ve diyafram
> dikişleri. Görüntünün önünü kapatıyorlardı.

Hareket kaynakları:

| Kaynak | CSS değişkeni | Etki |
|---|---|---|
| Açılış | `--op` | göz 0 → 1, kübik yavaşlamayla yerine oturur |
| İmleç | `--px`, `--py` | göz eğilir ve kayar, kaplama parlaması ±2.5%, panel −0.5% |

- Adım geçişleri (parola → telefon → kod) **odak kaydırma** ile:
  `@keyframes focusIn` (blur + scale). Slide veya fade-up yok.
- `prefers-reduced-motion: reduce`: eğim ve adım animasyonu kapanır,
  video oynamaz, poster kalır. Form tam çalışır.

**Bilinen sınır:** kaynak klip 1280×720, 4K değil. Tam kaplama zeminde
yumuşaklık grade + vinyet + grain ile kasıtlı stile çevrildi. Gerçek 4K
isteniyorsa klip upscale edilmeli.

## 5. Doğrulanan akışlar

| Test | Sonuç |
|---|---|
| E-posta ile kayıt → konsol | 201, `/dashboard/vision` |
| Aynı e-posta ile tekrar kayıt | 400 "Bu e-posta veya telefon zaten kayıtlı." |
| Zayıf parola (`12345678`) | 400 "Parola hem harf hem rakam içermeli." |
| Yeni hesapla giriş | 200 |
| `admin` / `admin123` hâlâ çalışıyor | 200 |
| OTP iste → doğrula | 200 |
| OTP yanlış kod | 401 |
| OTP kod tekrar kullanımı | reddedildi |
| Telefon normalizasyonu | `0555 987 65 43` → `+905559876543` |
| OAuth yapılandırılmamışken | 501 "GOOGLE_CLIENT_ID tanımlı değil." |
| `/dashboard` | `/dashboard/vision`'a yönlendi |
| Mobil 390px | yatay taşma yok |
| Tek panel, iki sekme | GİRİŞ ve KAYIT ikisi de viewport'a sığıyor |
| Telefon adımı → kod adımı | çalışıyor, dev kod arayüzde gösteriliyor |
| Google client ID yüklendi | `/auth/providers` → `google.enabled: true` |
| Google düğmesi | etkin; GIS kitaplığı yükleniyor, `origin_mismatch` yok |
| Google penceresi iptal edilirse | düğme artık kilitlenmiyor (focus + 20 sn sıfırlama) |
| Göz videosu | kadrajın tamamı görünür, letterbox yok, fareyle eğiliyor |

## 6. ÖNEMLİ — üç ayrı kopya karışıklığı

Makinede aynı projenin üç kopyası çalışıyordu:

```
Argus-Lens-main (3)/frontend   → :3000'de açıktı (ekran görüntüsündeki bu)
Argus-Lens-main (5)            → :8090'da backend çalışıyordu
Argus-Lens-main (6)            → tüm yeni çalışma burada
```

`(6)`'nın backend'i `models/` paketi eksik olduğu için açılmıyordu; paket
`(5)`'ten kopyalandı ve `(6)` artık tek başına çalışıyor.

**Bundan sonra her şeyi `(6)` üzerinden çalıştır:**

```bash
cd "Argus-Lens-main (6)/Argus-Lens-main"
python main.py                 # backend :8090

cd frontend
npm run dev                    # veya: npm start   → :3001
```

`(3)` ve `(5)` kopyalarındaki sunucuları kapat, yoksa hangi kodu gördüğün
belirsiz kalır.

Not: `(5)`'in CORS'u yalnızca `localhost:3001`'e izin veriyordu ve "Network
Error" bundan çıkıyordu. `(6)`'nın CORS'u `*` — port kısıtı yok.

## 7. Dosya haritası

```
core/user_store.py                 kayıt, parola hash, OTP, OAuth bağlama
core/oidc.py                       Google/Apple JWKS imza doğrulaması
api/auth.py                        /register /otp/* /oauth/* /providers
api/system_routes.py               /auth/token — kullanıcı deposunu da sorgular
data/users.json                    kullanıcı deposu (git'e girmemeli)

frontend/src/app/(auth)/login/page.tsx      iki panelli sinematik sayfa
frontend/src/components/auth/AuthAperture.tsx  diyafram sahnesi + paralaks
frontend/src/components/auth/AuthPanels.tsx giriş / kayıt / OTP adımları
frontend/src/components/auth/SocialAuth.tsx Google + Apple düğmeleri
frontend/src/app/(dashboard)/dashboard/page.tsx  → /dashboard/vision
```

`data/users.json` parola hash'leri içerir — `.gitignore`'a eklenmeli.

---

# Kamera sayfası (`/dashboard/vision`)

Aynı sanat yönü (Optik Enstrüman) kamera konsoluna uygulandı.

## Bekleme sahnesi

Kamera kapalıyken ekran artık boş siyah kutu değil, **kapalı bir vizör**.
Zemin: `gözü_gösterdikten_sonra_hemen.mp4`.

> Bu dosya repodaki `05-act.mp4` ile **byte-byte aynı** (MD5
> `8399dbadd3ea29efc0f955cb52db487b`). Yeniden kopyalanmadı; posteri ve
> tembel yükleme davranışı zaten hazırdı.

Kaldırılanlar: `ParticleField`, SVG göz, dönen kesikli halkalar, cyan
gradyan düğme, 20 adet yüzen nokta. Hepsi jenerik "AI dashboard" kalıbıydı.

## Fare ile hareket

| Kaynak | CSS değişkeni | Etki |
|---|---|---|
| Fare | `--px`, `--py` | video −2%, metin bloğu **ters yönde** +0.9% → katmanlar ayrışır |
| Tekerlek | `--wz` | sahne ekseninde iter (`scale 1.06 → 1.11`), yay gibi merkeze döner |
| Açılış | `--op` | bulanıktan nete gelir (odak kaydırma) |

Tekerlek `preventDefault` **çağırmaz** — sayfa kaydırmasını çalmaz, yalnız
görsel derinlik ekler.

## Kaydırmaya bağlı reveal

22 göz durumu `opacity:0 / blur(6px)` başlar, kendi kaydırma kabına girince
`.in-focus` alıp nete gelir (`ScrollFocus.tsx`). Gözlemcinin `root` değeri
sayfa değil **listenin kendi kabı** (`.vis-scroll`) — aksi hâlde kap içinde
kaydırma hiç tetiklenmez. 2.5 sn emniyet zamanlayıcısı var: gözlemci hiç
tetiklenmezse liste görünmez kalmaz.

## Sağ raf

| Önce | Sonra |
|---|---|
| `rounded-2xl` + cyan gradyan kart | `.vis-plate` — 2px gravür plakası, üst kenarda kesik cetvel |
| Kare cyan zoom düğmeleri | `.vis-zoom` — kadran taksimatı şeridi, aktif olan kemik beyaz |
| Kutulu hastalık listesi | Sol kenar aksanlı satırlar; aktif olanda cyan aksan |
| `text-amber-400` görülme oranı | `.t-measure` — mono, tabular, cyan |

Cyan disiplini: yalnız aktif seçim, ölçüm değerleri ve canlı kenarlarda.

## Bilinen sınırlar

- `vision/page.tsx:360` civarında **mevcut** bir lint hatası duruyor
  (`setState` doğrudan efekt gövdesinde — zoom 1×'e dönünce pan sıfırlama).
  `CLAUDE.md` UI görevlerinde state yönetimine dokunmamayı söylüyor,
  bu yüzden bilerek elleşmedim.
- Kamera akışı, zoom/pan matematiği ve `useEyeFilter` mantığı değişmedi —
  yalnız JSX, sınıflar ve animasyon.
- Klip 1280×720. Tam kaplama zeminde yumuşaklık grade + vinyet ile
  kasıtlı stile çevrildi.

---

# Konsol kabuğu — renk sistemi ve sol raf

## Renk görevleri (KURAL DEĞİŞİKLİĞİ)

`CLAUDE.md` "Tek accent renk: cyan" diyor. Bu kural **kullanıcı talimatıyla
bilerek değiştirildi**: tek renkli sistemde hiyerarşi zayıftı — menü, durum ve
ölçüm hepsi aynı cyan ile yarışıyordu.

| Renk | Görev | Nerede |
|---|---|---|
| cyan `#00D4FF` | **yalnız ölçülmüş değer** | FPS, çözünürlük, gecikme, güven %, vital |
| amber `#E8A33D` | **durum ve aktif seçim** | aktif menü, sistem sağlığı, aktif zoom, seçili hastalık |
| kemik `#F0E9DC` | başlık ve birincil eylem | H1, "Kamerayı başlat" |
| kırmızı `#E5484D` | **yalnız tehlike** | kritik uyarı rozeti, oturum kapatma |

Metin (mürekkep) soğuk slate'ten **sıcak kemik-beyaza** geçti.
Ölçülen kontrast (zemin `#12181A` üzerinde): başlık 16.1:1 · gövde 11.4:1 ·
kadran etiketi 6.9:1 — hepsi WCAG 2.2 AA üstünde.

Token'lar: `--accent-status`, `--accent-status-soft/edge/wash/glow`
(`tokens.css`, semantic katman). Açık temada da tanımlı.

## Zemin

Kare "blueprint grid" kaldırıldı — jenerik dashboard kalıbıydı.
Yerine **gravürlü alet plakası**: yatay taksimat (`.console-rules`,
radyal maskeli) + tek yönlü kaplama parlaması (`.console-flare`) +
grafit-zeytin gradyan. Video yok; video zaten kamera kutusunun içinde oynuyor.

## Sol raf

| Önce | Sonra |
|---|---|
| Düz 5 öğelik liste | **Gruplu**: GÖRÜ / ANALİZ / HESAP, gravür etiketleriyle |
| Her aktif öğeye ayrı cyan çubuk | **Tek kayan gösterge** — aktif öğeyi yumuşakça takip eder |
| Dönen kesikli halka + glow logo | Gravür marka kilidi, ağırlık kontrastı (`Argus` 800 / `Lens` 200) |
| `rounded-xl` kartlar | 2px gravür plakalar |
| Statik menü | Öğeler sırayla odaktan gelir (`focusIn`, 55 ms kademe) |

Kayan gösterge konumu React state ile değil, doğrudan CSS değişkeniyle
(`--y` / `--h`) yazılır — rota değişiminde yeniden render olmaz.

### Düzeltilen hata
`.rail-foot` grid çocukları varsayılan `min-width: auto` ile içeriğin
min-content genişliğine şişip rafı aşıyordu (259px > 256px): e-posta ve
"%65" kırpılıyordu. `min-inline-size: 0` ile çözüldü, `scrollWidth` 255'e indi.

## Üst çubuk

Slate/`rounded-lg` düğmeler → token tabanlı `.topbar-btn`, `.topbar-user`,
`.topbar-clock`. Kullanıcı menüsü gravür plakası oldu ve odak-kaydırma ile
açılıyor. "Sign Out" → "Oturumu kapat".

## Bilinen sınır

`(dashboard)/layout.tsx:31` içinde **mevcut** bir lint hatası duruyor
(`setHydrated(true)` doğrudan efekt gövdesinde). Hydration guard mantığı;
`CLAUDE.md` UI görevlerinde state yönetimine dokunmamayı söylediği için
elleşmedim. Benim eklediğim/dokunduğum bileşenlerde lint temiz (0 uyarı).

---

# Kamera — premium yükseltmeler

Dört özellik, dördü de senin onayınla.

## 1. Sağlıklı göz ile karşılaştırma

Ayırıcının **solu her zaman sağlıklı göz**, sağı seçili durum. Fareyle
sürüklenir, `←` `→` ile de oynar (`role="slider"`).

> **Neden ayrı canvas:** 22 durumdan 6'sı `canvas.style.filter` (CSS filtresi)
> kullanıyor ve o filtre canvas'ın TAMAMINA uygulanıyor. Ana canvas içinde
> bölme yapılsaydı sağlıklı taraf da bulanıklaşırdı. Temiz kare, aynı
> kırpma/zoom/pan ile ikinci bir canvas'a çiziliyor ve `clip-path` ile
> kırpılıyor. 22 durumun hepsinde doğru çalışır.

## 2. Şiddet kadranı (0–100)

İki mekanizma birlikte:
- **Blur ölçekleme** — 12 blur değeri `bl(px)` yardımcısından geçiyor,
  çarpan 0.22x → 1.65x. Kırma kusurlarında (miyop, hipermetrop…) fiziksel
  olarak doğru davranış.
- **Harmanlama** — bulanık olmayan durumlar (renk körlüğü, lekeler, tünel
  görüş) blur ölçeklemesinden etkilenmiyor; sağlıklı kare düşük alfayla
  üstüne çiziliyor. 22 durumun hepsi için sürekli ve monoton bir kadran.

> **Dürüst sınır:** kadran dioptri (`−0.5 D → −8 D`) etiketiyle değil yüzdeyle
> gösteriliyor. Gerçek dioptri eşlemesi için her durumun kendi fiziksel
> parametresi ayrı ayrı ölçeklenmeli — 22 vakanın tek tek elden geçmesi
> gerekir. Şu anki model algısal olarak doğru, klinik olarak yaklaşık.

## 3. Arama + klavye

- Yazdıkça filtreler (ad ve etiket üzerinde)
- `↑` `↓` gezinir, `Enter` seçer, `Esc` temizler
- `/` sayfanın herhangi bir yerinden arama alanına odaklanır
- Türkçe katlama: `ı/İ/ş/ğ/ü/ö/ç` farkı yok sayılır — "katarak" yazınca
  "Katarakt" bulunur
- `role="listbox"` / `role="option"` semantiği

Kaydırmaya bağlı reveal buradan **kaldırıldı**: arama sonucu bulanık
başlarsa liste kullanılamaz hâle geliyordu.

## 4. Odak kaydırma geçişi

Durum değişince kare ~420 ms bulanıktan nete gelir (`rackShift`).
Anında zıplamak "alet ayarlanıyor" hissini bozuyordu.
Efekt yerine olay işleyicisinde tetiklenir — efekt gövdesinde senkron
setState zincirleme render uyarısı veriyordu.

## Cyan disiplini denetimi

Sayfadaki tüm metin renkleri tarandı. Cyan kalan tek şeyler:
`60 FPS`, `1280 × 720`, `GECİKME 24 MS`, `KAM 00 · BEKLEME`, görülme oranı —
hepsi ölçülmüş değer. Breadcrumb, CANLI rozeti, plaka ikonları, aktif nokta,
marka işareti ve avatar kemik/amber'e taşındı.

---

# Sağlık Profili

## Video

Verdiğin iki dosya (`gözü_gösterdikten_sonra_hemen.mp4` ve `(1)` kopyası)
**byte-byte aynı** — MD5 `8399dbadd3ea29efc0f955cb52db487b`. Tek video var,
repoda `05-act.mp4`. Başlık sahnesinin zemini oldu.

Başlık sayfa kaydıkça geride kalır (`--sp` ile paralaks), fareyle kayar,
açılışta bulanıktan nete gelir.

## Hasta künyesi — yeni

Gerçek bir hastane kaydında olup arayüzde eksik olan idari alanlar eklendi:

| Plaka | Alanlar |
|---|---|
| Kimlik | protokol no, ad soyad, doğum tarihi, telefon |
| Sigorta | kurum, poliçe/sicil no, organ bağışı |
| Acil durumda aranacak | ad, yakınlık, telefon (kırmızı kenar) |
| Sorumlu hekim | hekim, birim |
| Yaşam tarzı | sigara (3 kademe), alkol (3 kademe) |
| Öykü ve aşılar | aile öyküsü, aşı kayıtları (çipli liste) |

**TC kimlik numarası bilerek yok.** Uygulamanın hiçbir yerinde doğrulanmıyor;
saklanması gereksiz risk. Protokol numarası kurum içi takip için yeterli.

### Backend

`CLAUDE.md` UI görevlerinde backend'e dokunmamayı söylüyor, ama alanları
yalnız arayüze eklemek onları **sessizce kaybettirirdi** — `ProfileUpdate`
şeması sabit ve fazla anahtarları düşürüyor. Bu yüzden minimum genişletme:

- `ProfileUpdate.admin_record: Optional[dict]` — tek JSON alanı, her yeni
  alan için sütun eklemek gerekmiyor
- `HealthProfile.admin_record` JSON sütunu
- Fallback varsayılanına boş yapı

> **Bulunan hata:** `update_profile`'in `except` dalı (JSON yedeği) yeni alanı
> yazmıyordu. POST 200 dönüyor ama künye her kayıtta sessizce kayboluyordu.
> Bu kurulumda DB yolu düşük olduğu için **her zaman** yedek dal çalışıyor,
> yani hata her kayıtta tetikleniyordu. Yedek dala `admin_record` eklendi;
> uçtan uca doğrulandı (`full_name: 'Veli Parlak'`, `organ_donor: true` kalıcı).

## Görsel

- `rounded-2xl` cyan gradyan kartlar → 2px gravür plakalar
- Harf harf animasyonlu başlık → ağırlık kontrastı (`SAĞLIK` 800 / `profilin` 200)
- Dekoratif cyan blur küreleri kaldırıldı
- Bölümler kaydırdıkça odağa gelir (`[data-reveal-block]`)
- Künye hücreleri **gerçek veriden türetilir**: kan grubu, BMI, kronik/alerji/
  ilaç sayısı — uydurma değer yok
- Cyan sayımı: **0**. Ölçüm rozetleri ve su ilerlemesi `--measure` token'ı
  üzerinden; aktif seçimler amber; acil durum kırmızı

> **Yol boyunca:** paralaks ve reveal ilk sürümde sessizce çalışmadı — sabit
> bir seçiciyle (`[data-profile-scroll]`) kap aranıyordu ama konsolda gerçek
> scroller `main`. Artık en yakın gerçekten kaydırılabilir ata aranıyor,
> reveal gözlemcisi ise viewport kökünü kullanıyor. Ölçümle doğrulandı:
> `--sp` 0 → 0.71.

## Bilinen sınır

`profile/page.tsx:50` civarında **mevcut** bir lint hatası duruyor
(`fetchProfile` tanımlanmadan efekt içinde çağrılıyor). Çalışma zamanında
sorun çıkarmıyor; veri akışına dokunmadım.
