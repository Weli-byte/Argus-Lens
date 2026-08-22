# Google ve Apple ile giriş — kurulum

Kod tarafı **bitti ve test edildi**. Eksik olan tek şey senin kendi
**istemci kimliğin (client ID)**. Bunu ben oluşturamam: kimlik senin Google /
Apple hesabına bağlı bir kayıt ve o hesaba giriş yapman gerekiyor.

Kimliği aldıktan sonra yapılacak tek şey onu **backend ortamına yazıp
backend'i yeniden başlatmak**. Frontend'i yeniden derlemeye gerek yok —
istemci kimliği çalışma zamanında `/api/v1/auth/providers` ucundan okunuyor.
(Bunu sahte bir kimlikle test ettim: düğme anında etkinleşti.)

---

## A. Google — ücretsiz, ~5 dakika

### 1. Proje oluştur
1. https://console.cloud.google.com adresine gir.
2. Üst çubukta proje seçiciye tıkla → **New Project**.
3. Ad: `ArgusLens` → **Create**.

### 2. OAuth izin ekranını yapılandır
1. Sol menü → **APIs & Services** → **OAuth consent screen**.
2. **User Type**: *External* → **Create**.
3. Doldur:
   - App name: `ArgusLens`
   - User support email: kendi e-postan
   - Developer contact: kendi e-postan
4. **Save and Continue** → Scopes ekranında bir şey ekleme → **Save and Continue**.
5. **Test users** ekranında **+ ADD USERS** → giriş yapacağın Gmail adresini ekle.
   > Uygulama "Testing" modundayken **yalnızca buraya eklediğin hesaplar**
   > giriş yapabilir. Herkese açmak için sonradan *Publish app* dersin.
6. **Save and Continue** → **Back to Dashboard**.

### 3. İstemci kimliğini oluştur
1. Sol menü → **APIs & Services** → **Credentials**.
2. **+ CREATE CREDENTIALS** → **OAuth client ID**.
3. **Application type**: *Web application*.
4. Ad: `ArgusLens Web`.
5. **Authorized JavaScript origins** → **+ ADD URI**, şunları ekle:
   ```
   http://localhost:3001
   ```
   > Uygulamayı başka bir portta veya alan adında açacaksan onu da ekle.
   > Google burada **tam eşleşme** arar; port farkı bile hata verir.
6. **Authorized redirect URIs**: Google Identity Services açılır pencere
   modunda çalıştığı için **boş bırakabilirsin**.
7. **CREATE**.
8. Çıkan kutudaki **Client ID**'yi kopyala. Şuna benzer:
   ```
   123456789012-abcdefghijklmnopqrstuvwxyz123456.apps.googleusercontent.com
   ```
   > **Client secret'a ihtiyacın yok** ve onu kimseyle paylaşma.
   > Bu akışta yalnızca client ID kullanılıyor.

### 4. Backend'e tanıt

**Windows PowerShell** (kalıcı, bir kez):
```powershell
setx GOOGLE_CLIENT_ID "buraya-client-id"
```
Sonra **yeni bir terminal aç** ve backend'i başlat.

Ya da tek seferlik (o terminal için):
```powershell
$env:GOOGLE_CLIENT_ID = "buraya-client-id"
python main.py
```

**Git Bash / WSL:**
```bash
GOOGLE_CLIENT_ID="buraya-client-id" python main.py
```

### 5. Doğrula
```bash
curl -s http://127.0.0.1:8090/api/v1/auth/providers
```
Beklenen:
```json
{"google":{"enabled":true,"client_id":"…"},"apple":{"enabled":false,"client_id":""}}
```
`/login` sayfasını yenile — **Google ile devam et** düğmesi etkinleşir.

---

## B. Apple — ücretli, ~20 dakika

Apple ile giriş **Apple Developer Program üyeliği** ister: **yılda 99 USD**.
Ücretsiz yolu yok. Üyeliğin varsa:

1. https://developer.apple.com/account → **Certificates, IDs & Profiles**.
2. **Identifiers** → **+** → *App IDs* → bir App ID oluştur
   (örn. `com.arguslens.app`), **Sign In with Apple** yeteneğini işaretle.
3. Tekrar **Identifiers** → **+** → *Services IDs* → oluştur
   (örn. `com.arguslens.web`). Bu değer senin **APPLE_CLIENT_ID**'in olacak.
4. Services ID'yi düzenle → **Sign In with Apple** → **Configure**:
   - Primary App ID: yukarıdaki App ID
   - Domains: `localhost` yerel testte kabul edilmez; gerçek bir alan adı
     ve **HTTPS** gerekir. Yerel deneme için `ngrok` gibi bir tünel kullan.
   - Return URLs: `https://alanadin.com/login`
5. Backend'e tanıt:
   ```powershell
   setx APPLE_CLIENT_ID "com.arguslens.web"
   ```

> **Apple'ın iki katı kısıtı var:** HTTPS zorunlu ve `localhost` çalışmaz.
> Bu yüzden Apple girişi ancak siteyi gerçek bir alan adına aldığında
> test edilebilir. Google'da böyle bir kısıt yok.

---

## Sık karşılaşılan hatalar

| Belirti | Sebep | Çözüm |
|---|---|---|
| Düğme hâlâ soluk | Backend yeniden başlatılmadı | Backend'i kapat/aç, `/auth/providers` çıktısını kontrol et |
| `origin_mismatch` | Origin listede yok | Google Console → Credentials → *Authorized JavaScript origins*'a `http://localhost:3001` ekle |
| `idpiframe_initialization_failed` | Üçüncü taraf çerezleri kapalı | Tarayıcı ayarından siteye izin ver |
| `403 access_denied` | Hesap test kullanıcısı değil | OAuth consent screen → *Test users*'a Gmail'ini ekle |
| Sunucu `401 Kimlik token'ı doğrulanamadı` | Backend'deki `GOOGLE_CLIENT_ID` frontend'in kullandığından farklı | İkisinin aynı olduğundan emin ol |
| Sunucu `501 tanımlı değil` | Ortam değişkeni okunamadı | `setx` sonrası **yeni terminal** açmayı unutma |

---

## Kod tarafında ne var

- `core/oidc.py` — Google/Apple JWKS ile **gerçek imza doğrulaması**
  (RS256/ES256, `aud` + `iss` + `exp` + `sub` zorunlu). İmzası
  doğrulanmamış token asla kabul edilmez.
- `api/auth.py` — `POST /auth/oauth/google`, `POST /auth/oauth/apple`,
  `GET /auth/providers`.
- `frontend/src/components/auth/SocialAuth.tsx` — sağlayıcı kitaplığını
  yükler, kimlik token'ını alır, sunucuya doğrulatır.
- Yapılandırma yoksa düğme **sessizce ölmez**: devre dışı görünür,
  sebebini yazar, uç 501 + açık mesaj döner.
