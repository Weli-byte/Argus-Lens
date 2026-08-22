# Dil katmanı — TR / EN

Arayüzün tamamı iki dilde çalışır. Seçim üst çubuktaki **TR / EN** anahtarından
yapılır; giriş ekranında da aynı anahtar sağ üstte durur, böylece kullanıcı
oturum açmadan önce de dilini seçebilir.

## Nasıl çalışıyor

`src/lib/i18n.tsx` tek dosya:

- `LocaleProvider` — `src/app/providers.tsx` içinde kökte
- `useT()` — yalnız çeviri fonksiyonu gerekiyorsa
- `useLocale()` — `{ t, locale, setLocale }`
- `pct(değer, locale)` — yüzde işaretinin yeri dile göre değişir: `%60` / `60%`

### Anahtar = Türkçe metnin kendisi

```tsx
const t = useT();
<h2>{t("Göz Durumu")}</h2>          // TR: Göz Durumu · EN: Eye Condition
```

`t("nav.camera")` gibi soyut anahtarlar yerine Türkçe metnin kendisi anahtar.
İki sebep:

1. Arayüz baştan Türkçe yazılmıştı; soyut anahtarlara geçmek her dosyada her
   metni yeniden adlandırmak demekti.
2. **Çevirisi olmayan metin sessizce Türkçe kalır.** Kırık bir `nav.camera`
   etiketi ekranda hiç görünmez — en kötü durumda kullanıcı Türkçe görür.

Yeni bir metin eklerken: JSX'te `t("Yeni metin")` yaz, sonra `i18n.tsx`
içindeki `EN` sözlüğüne `"Yeni metin": "New text",` satırını ekle. Sözlüğe
eklemeyi unutursan hata çıkmaz, metin Türkçe kalır.

### Seçim nerede tutuluyor

`localStorage["argus-locale"]`. Okuma `useSyncExternalStore` ile yapılır,
`useEffect` + `setState` ile değil. Sebep:

- Efekt içinde setState zincirleme render tetikler (React Compiler bunu hata
  sayar).
- Sunucu "tr" render ederken istemci ilk render'da kayıtlı değeri okur —
  sayfa açılışında bir kare Türkçe yanıp sönmez.

`storage` olayı da dinlenir: ikinci bir sekmede dil değişirse bu sekme de
anında döner.

`<html lang>` her değişimde güncellenir. Türkçe büyük/küçük harf kuralları
(`i` → `İ`) buna bağlı olduğu için bu şart.

## Kapsam

Çevrilen:

- Sol raf, üst çubuk, kullanıcı menüsü
- Giriş / kayıt ekranı — düğmeler, alan etiketleri, **hata ve bilgi mesajları**
  dâhil (EN seçiliyken "Sunucuya ulaşılamadı" gibi bir uyarı Türkçe kalmaz)
- Kamera: 22 göz hastalığının adı, etiketi, açıklaması ve görülme oranı
- Nesne tespiti, vital değerler, AI asistan, sağlık profili
- Asistanın karşılama mesajı ve hazır soruları — **gönderilen metin de**
  çevrilir, yoksa model Türkçe soru alıp Türkçe yanıtlardı
- Backend'den gelen NEWS2 durum değerleri (`Stabil`, `Yüksek Risk / Kritik` …)

Bilerek çevrilmeyen:

- **Hasta kaydı içeriği** — hekim adları, tanılar, aile öyküsü. Bunlar kayıt
  verisi; çevirmek kaydı yanlış temsil eder.
- **Tıbbi kısaltmalar ve birimler** — HR, SpO₂, NIBP, ECG, NEWS2, bpm, mmHg,
  mcg/dL. İki dilde de aynı.
- **E-Nabız** — özel ad.
- **Videoya gömülü yazılar** — tespit sahnesindeki "araba 95%", "yaya"
  etiketleri videonun kendisinde; kodla değiştirilemez.
- **Saat biçimi** — konsolun tamamı 24 saat kullanıyor, `toLocaleTimeString`
  çağrıları `tr-TR` ile 24 saatte kalıyor. `en-US`'a geçmek AM/PM getirirdi.

## Sözlük

`i18n.tsx` içindeki `EN` nesnesi, 416 benzersiz anahtar. Yinelenen anahtar
yok — JS nesnesinde yinelenen anahtar sessizce üzerine yazar, bu yüzden
eklemeden önce metnin sözlükte olup olmadığına bak.

## Düğmenin görünümü

`LocaleSwitch.tsx` + `globals.css` içindeki `.lang-switch*`. Sol raftaki aktif
menü göstergesiyle aynı hareket dili: seçim yanıp sönmez, altındaki işaretçi
kayar. Aktif seçim **amber** — palet kuralında amber "durum ve aktif seçim",
cyan yalnız ölçülmüş değer.
