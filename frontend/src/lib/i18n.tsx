"use client";

import React, {
  createContext,
  useContext,
  useMemo,
  useSyncExternalStore,
} from "react";

/* ────────────────────────────────────────────────────────────────────────────
   DİL KATMANI — TR / EN

   Anahtar olarak TÜRKÇE metnin kendisi kullanılır. Sebep: arayüzün tamamı
   Türkçe yazılmış; `t("nav.camera")` gibi soyut anahtarlara geçmek her
   dosyayı yeniden adlandırmak demekti. Bu yaklaşımla `t("Kamera")` yazmak
   yeterli ve çevirisi olmayan metin sessizce Türkçe kalıyor — kırık bir
   `nav.camera` etiketi ekranda görünmüyor.

   Seçim localStorage'da tutulur ve <html lang> güncellenir; Türkçe büyük
   harf kuralları (i → İ) buna bağlı olduğu için bu şart.
   ────────────────────────────────────────────────────────────────────────── */

export type Locale = "tr" | "en";

const STORAGE_KEY = "argus-locale";

/** Türkçe metin → İngilizce karşılığı. Eksik anahtar Türkçe kalır. */
const EN: Record<string, string> = {
  // ── Gezinme / kabuk ──
  "Görü": "Vision",
  "Analiz": "Analysis",
  "Hesap": "Account",
  "Kamera": "Camera",
  "Nesne Tespiti": "Object Detection",
  "Vital Değerler": "Vitals",
  "AI Asistan": "AI Assistant",
  "Sağlık Profilim": "Health Profile",
  "Biyonik lens": "Bionic lens",
  "Konsol gezinmesi": "Console navigation",
  "Aktif": "Active",
  "Çıkış yap": "Sign out",
  "Oturumu kapat": "Sign out",
  "Rafı genişlet": "Expand rail",
  "Rafı daralt": "Collapse rail",
  "Uyarı yok": "No alerts",
  "kritik uyarı": "critical alerts",
  "operatör": "operator",

  // ── Kamera ──
  "ArgusLens": "ArgusLens",
  "CANLI": "LIVE",
  "Yaklaştırma": "Zoom",
  "Göz Durumu": "Eye Condition",
  "Bir göz hastalığı seçin": "Select an eye condition",
  "Şiddet": "Severity",
  "Hafif": "Mild",
  "Orta": "Moderate",
  "İleri": "Severe",
  "Durum şiddeti": "Condition severity",
  "Sağlıklı göz ile karşılaştır": "Compare with healthy eye",
  "Karşılaştırmayı kapat": "Close comparison",
  "Karşılaştırma ayırıcı": "Comparison divider",
  "SAĞLIKLI": "HEALTHY",
  "Bilgi": "Information",
  "Görülme oranı": "Prevalence",
  "Bu hastalık hakkında AI'a sor": "Ask AI about this condition",
  "Göz durumu ara": "Search eye condition",
  "Ara — miyop, katarakt…": "Search — myopia, cataract…",
  "Göz durumları": "Eye conditions",
  "Eşleşme yok": "No match",
  "Görüntüyü taşımak için sürükleyin": "Drag to pan the image",
  "Görüntüyü keşfetmek için sürükleyin": "Drag to explore the image",
  "Sensör hazır · Yayın kapalı": "Sensor ready · Stream off",
  "Kamerayı başlat": "Start camera",
  "Kamera açıldığında görüntü tespit ve vital katmanlarıyla birlikte işlenir. Hiçbir kare cihazdan çıkmadan önce filtreden geçer.":
    "Once the camera is on, the feed is processed with the detection and vitals layers. No frame leaves the device before it passes the filter.",

  // ── Nesne tespiti ──
  "Nesne Tespiti · başlık": "Object Detection",
  "Kaynak bekleniyor": "Awaiting source",
  "GÖRSEL": "DROP",
  "bırak": "image",
  "Sürükleyip bırakın veya tıklayıp seçin. JPG, PNG, WebP — en fazla 10 MB. Görsel cihazdan çıkmadan önce tespit hattına girer.":
    "Drop a file or click to choose. JPG, PNG, WebP — 10 MB max. The image enters the detection pipeline without leaving the device.",
  "Görsel yükle veya sürükleyip bırak": "Upload or drop an image",
  "Tespit Sonuçları": "Detection Results",
  "Önce bir görsel yükleyin": "Upload an image first",
  "Görsel yüklenmedi": "No image loaded",
  "Tespit bekleniyor": "Awaiting detection",
  "Kutular Gizle": "Hide boxes",
  "Kutular Göster": "Show boxes",
  "Tümünü Göster": "Show all",
  "Temizle": "Clear",
  "Dışa Aktar": "Export",
  "Hazır:": "Presets:",
  "İnsan & Yüz": "People & Faces",
  "Araç": "Vehicles",
  "Hayvan": "Animals",
  "Mobilya": "Furniture",
  "Yiyecek": "Food",

  // ── Sağlık profili ──
  "Hasta kaydı · ArgusLens": "Patient record · ArgusLens",
  "Biyometrik ölçümler, klinik geçmiş ve optik kalibrasyon tek kayıtta. Veriler yalnız bu cihazda tutulur; dışarı çıkmadan önce filtreden geçer.":
    "Biometrics, clinical history and optical calibration in one record. Data stays on this device and passes the filter before it leaves.",
  "Kimlik": "Identity",
  "Protokol no": "Protocol no",
  "Ad soyad": "Full name",
  "Doğum tarihi": "Date of birth",
  "Telefon": "Phone",
  "Sigorta": "Insurance",
  "Kurum": "Provider",
  "Poliçe / sicil no": "Policy / member no",
  "Organ bağışı": "Organ donor",
  "Bağışçı": "Registered",
  "Kayıtlı değil": "Not registered",
  "Acil durumda aranacak": "Emergency contact",
  "Yakınlık": "Relationship",
  "Yakınının adı": "Next of kin",
  "Eş / kardeş / veli": "Spouse / sibling / guardian",
  "Sorumlu hekim": "Attending physician",
  "Hekim": "Physician",
  "Birim": "Department",
  "Yaşam tarzı": "Lifestyle",
  "Sigara": "Smoking",
  "Alkol": "Alcohol",
  "Hiç kullanmadı": "Never",
  "Bırakmış": "Former",
  "Aktif içici": "Current",
  "Kullanmıyor": "None",
  "Nadiren": "Occasional",
  "Düzenli": "Regular",
  "Öykü ve aşılar": "History & vaccines",
  "Aile öyküsü": "Family history",
  "Aşılar": "Vaccinations",
  "Kayıt yok": "No records",
  "Ekle": "Add",

  "Ad Soyad": "Full Name",
  "GG.AA.YYYY": "DD.MM.YYYY",
  "SGK / Özel": "Public / Private",
  "Göz Hastalıkları": "Ophthalmology",
  "Hipertansiyon (baba)": "Hypertension (father)",
  "Tetanoz (2024)": "Tetanus (2024)",
  "sil": "remove",

  // ── Göz hastalıkları (22 kayıt: ad, etiket, açıklama, görülme oranı) ──
  "Sağlıklı Göz": "Healthy Eye",
  "Sağlıklı bir gözde ışık tam olarak retina üzerinde odaklanır. Uzak ve yakın nesneler eşit netlikte görünür, renk algısı tamdır.":
    "In a healthy eye light focuses exactly on the retina. Near and distant objects appear equally sharp and colour perception is complete.",
  "Dünya nüfusunun yaklaşık %50'si.": "About 50% of the world population.",
  "Miyop": "Myopia",
  "Uzak Görememe": "Distance Blur",
  "Miyopi, gözün uzaktaki nesneleri net göremediği kırma kusurudur. Işık retina önünde odaklanır. Yakın nesneler net, uzak nesneler bulanık görünür.":
    "Myopia is a refractive error in which distant objects cannot be seen clearly. Light focuses in front of the retina. Near objects stay sharp while distant ones blur.",
  "Dünya nüfusunun yaklaşık %30'unda görülür.": "Occurs in about 30% of the world population.",
  "Hipermetrop": "Hyperopia",
  "Yakın Görememe": "Near Blur",
  "Hipermetropi, gözün yakındaki nesneleri net göremediği kırma kusurudur. Işık retina arkasında odaklanır. Uzak nesneler görece net, yakındakiler bulanık görünür.":
    "Hyperopia is a refractive error in which nearby objects cannot be seen clearly. Light focuses behind the retina. Distant objects stay relatively sharp while near ones blur.",
  "Dünya nüfusunun yaklaşık %25'inde görülür.": "Occurs in about 25% of the world population.",
  "Astigmat": "Astigmatism",
  "Astigmatizm": "Astigmatism",
  "Korneanın düzensiz eğriliğinden kaynaklanan bu kusurda görüntüler bulanık ya da çarpık görünür. Hem yakın hem uzak nesnelerde bozulma yaşanabilir.":
    "Caused by an irregular curvature of the cornea, this error makes images look blurred or distorted. Both near and distant objects can be affected.",
  "Dünya nüfusunun yaklaşık %33'ünde görülür.": "Occurs in about 33% of the world population.",
  "Presbiopi": "Presbyopia",
  "Yaşa Bağlı Yakın Görememe": "Age-Related Near Blur",
  "40 yaş sonrasında göz merceğinin esnekliğini kaybetmesiyle yakın mesafedeki nesneler bulanıklaşır. Okuma mesafesinde odaklanma güçleşir, uzak görüş etkilenmez.":
    "After the age of 40 the lens loses its elasticity and objects at close range blur. Focusing at reading distance becomes difficult while distance vision is unaffected.",
  "Dünya nüfusunun yaklaşık %25'ini, 40 yaş üstünde çoğunluğu etkiler.":
    "Affects about 25% of the world population and the majority of people over 40.",
  "Şaşılık": "Strabismus",
  "Çift Görme (Diplopi)": "Double Vision (Diplopia)",
  "Strabismus veya şaşılıkta gözler farklı yönlere bakarak çift görme oluşturur. İki göz görüntüsü üst üste binmez; diplopi yani ikili imge meydana gelir.":
    "In strabismus the eyes point in different directions and produce double vision. The two retinal images do not overlap, creating diplopia — a doubled image.",
  "Dünya nüfusunun yaklaşık %4'ünde görülür.": "Occurs in about 4% of the world population.",
  "Nistagmus": "Nystagmus",
  "Göz Titremesi": "Eye Tremor",
  "Gözlerin istemsiz, ritmik hareketi nedeniyle görüntü sürekli titrer veya kayar. Görme netliği düşer, baş dönmesi eşlik edebilir.":
    "Involuntary rhythmic eye movement makes the image shake or drift continuously. Visual acuity drops and dizziness may accompany it.",
  "Yaklaşık 1.000 kişide 1-2'sinde görülür.": "Occurs in about 1–2 of every 1,000 people.",
  "Ambliyopi": "Amblyopia",
  "Tembel Göz": "Lazy Eye",
  "Beyin, zayıf gözden gelen görüntüyü bastırır; o göz zamanla işlevini yitirir. Genellikle çocuklukta başlar, erken tedavi oldukça önemlidir.":
    "The brain suppresses the image from the weaker eye and that eye gradually loses function. It usually starts in childhood, where early treatment matters a great deal.",
  "Çocukların yaklaşık %2-3'ünde görülür.": "Occurs in about 2–3% of children.",
  "Kırmızı-Yeşil Renk Körlüğü": "Red-Green Colour Blindness",
  "Deuteranopi": "Deuteranopia",
  "Yeşil konları eksik olan kişilerde kırmızı ve yeşil renkler birbirinden ayırt edilemez. En sık rastlanan renk körlüğü türüdür.":
    "People missing green cones cannot tell red and green apart. It is the most common type of colour blindness.",
  "Erkeklerin %8'ini, kadınların %0,5'ini etkiler.": "Affects 8% of men and 0.5% of women.",
  "Mavi-Sarı Renk Körlüğü": "Blue-Yellow Colour Blindness",
  "Tritanopi": "Tritanopia",
  "Mavi konların yokluğuyla oluşan bu nadir renk körlüğünde mavi ve sarı renkler karışır. Gökyüzü yeşilimsi, sarı ise pembemsi görünebilir.":
    "In this rare colour blindness caused by absent blue cones, blue and yellow are confused. The sky can look greenish and yellow pinkish.",
  "Dünya nüfusunun yaklaşık %0,01'inde görülür.": "Occurs in about 0.01% of the world population.",
  "Katarakt": "Cataract",
  "Göz Merceği Bulanıklığı": "Clouded Lens",
  "Katarakt, göz merceğinin zamanla bulanıklaşmasıyla oluşur. Görüntüler sisli ve sarımsı bir hal alır, kontrast duyarlılığı düşer.":
    "A cataract forms as the lens of the eye clouds over time. Images take on a hazy, yellowish cast and contrast sensitivity drops.",
  "60 yaş üstündeki bireylerin %50'sinden fazlasını etkiler.":
    "Affects more than 50% of people over 60.",
  "Keratokonus": "Keratoconus",
  "Kornea Konus Şekli": "Conical Cornea",
  "Korneanın incelerek konik şekil almasıyla ışık düzensiz kırılır. Işık kaynaklarının çevresinde hale ve ışın görülür; görüntüler hayalet izler oluşturur.":
    "As the cornea thins into a cone shape, light refracts irregularly. Halos and starbursts appear around light sources and images leave ghost trails.",
  "Yaklaşık 2.000 kişide 1'inde görülür.": "Occurs in about 1 of every 2,000 people.",
  "Glokom": "Glaucoma",
  "Tünel Görüşü": "Tunnel Vision",
  "Artmış göz içi basıncı görme sinirini hasarlandırarak periferik görmeyi yok eder. Sanki bir tünelin içinden bakıyormuş gibi yalnızca merkez net görünür.":
    "Raised intraocular pressure damages the optic nerve and destroys peripheral vision. Only the centre stays sharp, as if looking through a tunnel.",
  "Dünya nüfusunun yaklaşık %2'sinde görülür.": "Occurs in about 2% of the world population.",
  "Maküla Dejenerasyonu": "Macular Degeneration",
  "Merkezi Kör Alan": "Central Blind Spot",
  "Retinanın merkezi bölgesi (makula) hasar gördüğünde görüş alanının tam ortasında kör bir nokta oluşur. Periferik görme büyük ölçüde korunur.":
    "When the central region of the retina (the macula) is damaged, a blind spot forms in the very middle of the visual field. Peripheral vision is largely preserved.",
  "50 yaş üstü bireylerin yaklaşık %8,7'sini etkiler.": "Affects about 8.7% of people over 50.",
  "Diyabetik Retinopati": "Diabetic Retinopathy",
  "Kan Damarı Hasarı": "Blood Vessel Damage",
  "Diyabete bağlı retina kan damarları zedelendiğinde kanamalara bağlı koyu lekeler ve genel bir bulanıklık oluşur. İleri evrede görme tamamen kaybolabilir.":
    "When diabetes damages the retinal blood vessels, haemorrhages produce dark patches and an overall blur. Vision can be lost entirely at advanced stages.",
  "Diyabetli bireylerin yaklaşık %34'ünde görülür.":
    "Occurs in about 34% of people with diabetes.",
  "Periferik Görme Kaybı": "Peripheral Vision Loss",
  "Genetik kökenli bu hastalıkta retinanın çomak hücreleri ilerleyici biçimde tahrip olur. Periferik görme daralır, gece körlüğü ve fotopsi oluşur.":
    "In this genetic disease the rod cells of the retina are progressively destroyed. Peripheral vision narrows, with night blindness and photopsia.",
  "Dünya nüfusunun yaklaşık %0,04'ünü etkiler.": "Affects about 0.04% of the world population.",
  "Retina Dekolmanı": "Retinal Detachment",
  "Görüş Alanında Perde": "Curtain Over the Field",
  "Retinanın yerinden ayrılmasıyla görüş alanında bir taraftan başlayan karanlık perde hissi oluşur. Yanıp sönen ışık parlamaları eşlik edebilir; acil müdahale gerektirir.":
    "As the retina separates, a dark curtain seems to sweep in from one side of the visual field. Flashes of light may accompany it; it requires emergency care.",
  "Yılda 10.000 kişide yaklaşık 1'inde görülür.":
    "Occurs in about 1 of every 10,000 people per year.",
  "Leber Konjenital Amorozisi": "Leber Congenital Amaurosis",
  "Doğuştan Görme Kaybı": "Congenital Vision Loss",
  "Doğumsal retina distrofisi nedeniyle doğuştan ciddi görme azlığı ya da tam görme kaybı oluşur. Retina fotoalıcıları çalışmaz; yalnızca ışık-gölge farkı algılanabilir.":
    "Congenital retinal dystrophy causes severe vision impairment or total blindness from birth. The retinal photoreceptors do not function; only light and shadow may be perceived.",
  "100.000 doğumda yaklaşık 2-3 vakada görülür.": "Seen in about 2–3 of every 100,000 births.",
  "Optik Nörit": "Optic Neuritis",
  "Optik Sinir İltihabı": "Optic Nerve Inflammation",
  "Optik sinirin iltihaplanmasıyla görüş alanında merkezi kararma ve renk solgunluğu oluşur. Göz hareketi ile artan ağrı sık görülen belirtidir.":
    "Inflammation of the optic nerve darkens the centre of the visual field and washes out colour. Pain that increases with eye movement is a common symptom.",
  "Yılda 100.000 kişide yaklaşık 5'inde görülür.":
    "Occurs in about 5 of every 100,000 people per year.",
  "Hipertansif Retinopati": "Hypertensive Retinopathy",
  "Tansiyon Kaynaklı Retina Hasarı": "Blood-Pressure Retinal Damage",
  "Yüksek tansiyon retina kan damarlarını daraltarak görüşü bozar. Kenar bölgelerde kırmızımsı vasküler hasar belirtileri ve genel bulanıklık oluşur.":
    "High blood pressure narrows the retinal blood vessels and degrades vision. Reddish signs of vascular damage appear at the edges along with an overall blur.",
  "Hipertansif bireylerin yaklaşık %70'inde bulgu görülür.":
    "Findings appear in about 70% of people with hypertension.",
  "Üveit": "Uveitis",
  "Göz İçi İltihap": "Intraocular Inflammation",
  "Gözün orta tabakasının (uvea) iltihaplanmasıyla görüş bulanır, ışığa duyarlılık artar. Hafif yüzen lekeler (floaters) görüntüde belirginleşir.":
    "Inflammation of the middle layer of the eye (the uvea) clouds vision and increases light sensitivity. Faint floaters become prominent in the image.",
  "Görme kaybının %10-15'inden sorumludur.": "Responsible for 10–15% of vision loss.",
  "Fotofobi": "Photophobia",
  "Işık Hassasiyeti": "Light Sensitivity",
  "Işığa aşırı duyarlılık nedeniyle parlak ortamlarda şiddetli rahatsızlık ve görme bozukluğu yaşanır. Mümkün olan en parlak noktalar aşırı beyaz ve kamaştırıcı görünür.":
    "Extreme sensitivity to light causes severe discomfort and impaired vision in bright surroundings. The brightest points look excessively white and dazzling.",
  "Kronik migren hastalarının %80'inde, pek çok göz hastalığına eşlik eder.":
    "Present in 80% of chronic migraine patients and accompanies many eye diseases.",
  "Kırma Kusurları": "Refractive Errors",
  "Göz Hareketleri": "Eye Movement",
  "Renk Görme": "Colour Vision",
  "Kornea & Lens": "Cornea & Lens",
  "Retina Hastalıkları": "Retinal Disease",
  "Sinir & Damar": "Nerve & Vessel",
  "görüntü": "feed",
  "Görüntü konumu": "Image position",
  "Durdur": "Stop",
  "Ekran Görüntüsü": "Screenshot",

  "NESNE": "OBJECT",
  "tespiti": "detection",
  "TARA": "SCAN",
  "TARANYOR": "SCANNING",
  "TARANIYOR…": "SCANNING…",
  "Tespit ediliyor…": "Detecting…",
  "Sonuç bulunamadı": "No results",
  "Nesne adı yazın... (örn: araba, insan, bina)":
    "Type an object name… (e.g. car, person, building)",
  "İpucu — birden fazla nesne için virgülle ayırın: 'araba, insan, ağaç'":
    "Tip — separate multiple objects with commas: 'car, person, tree'",
  "Görseli kaldır": "Remove image",
  "Sonuçlarda ara…": "Search results…",

  // ── Konsol sayfaları: profil, vital, asistan ──
  "Sağlık Profili Yükleniyor...": "Loading health profile…",
  "SAĞLIK": "HEALTH",
  "profilin": "profile",
  "BİYOMETRİK ÖLÇÜMLER": "BIOMETRIC MEASUREMENTS",
  "Kan Grubu": "Blood Type",
  "Cinsiyet": "Sex",
  "Erkek": "Male",
  "Kadın": "Female",
  "BMI İNDEKSİ": "BMI INDEX",
  "E-NABIZ SAĞLIK GEÇMİŞİ": "E-NABIZ HEALTH HISTORY",
  "Entegre Sistem": "Integrated system",
  "Tarih": "Date",
  "Bölüm": "Department",
  "Tanı": "Diagnosis",
  "İlaçlar": "Medication",
  "Test": "Test",
  "Değer": "Value",
  "Durum": "Status",
  "E-NABIZ RAPORU YÜKLE (YAPAY ZEKA)": "UPLOAD E-NABIZ REPORT (AI)",
  "E-Nabız sisteminden alınan sağlık raporu PDF veya metin dosyası.":
    "A health report from the E-Nabız system as a PDF or text file.",
  "DOSYA SEÇ": "CHOOSE FILE",
  "E-Nabız verileri başarıyla sisteme aktarıldı!": "E-Nabız data imported successfully.",
  "YAPAY ZEKA KLİNİK EPİKRİZ": "AI CLINICAL SUMMARY",
  "Tüm biometrik profiliniz, geçmiş E-Nabız verileriniz ve ArgusLens anlık telemetriniz RAG ile analiz edilerek profesyonel bir klinik rapor üretilir.":
    "Your full biometric profile, past E-Nabız records and live ArgusLens telemetry are analysed with RAG to produce a professional clinical report.",
  "RAPOR ÜRETİLİYOR...": "GENERATING REPORT…",
  "RAPOR ÜRET": "GENERATE REPORT",
  "TIBBİ DURUM ETİKETLERİ": "MEDICAL CONDITION TAGS",
  "Kronik Hastalıklar": "Chronic Conditions",
  "Alerjiler": "Allergies",
  "Aktif İlaçlar": "Active Medication",
  "DONANIM KALİBRASYONU": "HARDWARE CALIBRATION",
  "BAĞLI": "CONNECTED",
  "IOP Baz Basıncı": "IOP Baseline",
  "Glikoz Katsayısı": "Glucose Coefficient",
  "Su Tüketimi": "Water Intake",
  "Hastalık ekle...": "Add a condition…",
  "Alerji ekle...": "Add an allergy…",
  "İlaç ekle...": "Add a medication…",
  "ARGUSLENS VİTAL MONİTÖR": "ARGUSLENS VITAL MONITOR",
  "Hasta No:": "Patient ID:",
  "Ad:": "Name:",
  "Yaş:": "Age:",
  "Servis:": "Unit:",
  "Biyonik lens sensor verileri bekleniyor...": "Waiting for bionic lens sensor data…",
  "NABIZ (bpm)": "HEART RATE (bpm)",
  "Tahmin (sonraki 15 sn)": "Prediction (next 15s)",
  "SİSTOLİK TANSİYON (mmHg)": "SYSTOLIC BP (mmHg)",
  "TREND ÖZETİ": "TREND SUMMARY",
  "Nabız": "Heart Rate",
  "Sistolik Tansiyon": "Systolic BP",
  "ANOMALİ İNDEKSİ": "ANOMALY INDEX",
  "Toplam anomali": "Total anomalies",
  "ANOMALİ": "ANOMALOUS",
  "TAHMİN (10 sn)": "PREDICTION (10s)",
  "PARAMETRE": "PARAM",
  "EN AZ / EN ÇOK": "MIN/MAX",
  "AI DOKTOR RAPORU": "AI PHYSICIAN REPORT",
  "ÜRETİLİYOR...": "GENERATING…",
  "GPT-4O RAPORU YAZ": "WRITE GPT-4O REPORT",
  "Rapor Hazır! (Aşağıya bakın)": "Report ready — see below.",
  "NABIZ": "HEART RATE",
  "Aralık: 60 - 100 | ECG": "Range: 60 - 100 | ECG",
  "Aralık: 95 - 100 | SpO₂": "Range: 95 - 100 | SpO₂",
  "TANSİYON": "BLOOD PRESSURE",
  "Aralık: 90-140/60-90 | NIBP": "Range: 90-140/60-90 | NIBP",
  "NEWS2 RİSK SKORU": "NEWS2 RISK SCORE",
  "0 - 4: GÜVENLİ": "0 - 4: SAFE",
  "5 - 6: DİKKAT": "5 - 6: CAUTION",
  "7+: TEHLİKE": "7+: DANGER",
  "İKİNCİL VİTAL BULGULAR": "SECONDARY VITAL SIGNS",
  "VÜCUT SICAKLIĞI": "TEMPERATURE",
  "SOLUNUM": "RESPIRATION",
  "GÖZ İÇİ BASINCI": "IOP (EYE)",
  "GÖZYAŞI GLİKOZU": "TEAR GLUCOSE",
  "KORTİZOL (STRES)": "CORTISOL (STRESS)",
  "SİSTEM DURUMU": "SYSTEM STATUS",
  "AI çıkarımı": "AI inference",
  "Etkin": "Active",
  "Model mimarisi": "Model architecture",
  "GPT-4O HEKİM RAPORU VE TIBBİ TAVSİYELER": "GPT-4O PHYSICIAN REPORT AND MEDICAL ADVICE",
  "KLİNİK RAPOR": "CLINICAL REPORT",
  "TAVSİYELER": "RECOMMENDATIONS",
  "Bağlantı: kurulu": "Connection: connected",
  "Veri akışı: canlı": "Data streaming: live",
  "AI motoru: çalışıyor": "AI engine: running",
  "Sunucu: arguslens-hub-01": "Server: arguslens-hub-01",
  "Sürüm: 4.0.0": "Version: 4.0.0",
  "YENİ SOHBET": "NEW CHAT",
  "Geçmiş": "History",
  "Kayıtlı sohbet bulunamadı.": "No saved conversations.",
  "ARGUSLENS KLİNİK ASISTAN": "ARGUSLENS CLINICAL ASSISTANT",
  "GPT-4o Medikal Zeka": "GPT-4o medical intelligence",
  "Klinik Triage Uyarısı:": "Clinical triage warning:",
  "Yapay zeka asistanının tıbbi önerileri teşhis amacı taşımaz. Acil durumlarda 112 Acil Yardım hattını arayınız.":
    "The assistant's medical suggestions are not a diagnosis. In an emergency call your local emergency number (112 in Türkiye).",
  "Klinik tıp veri tabanları ve vital veriler inceleniyor...":
    "Searching clinical databases and vital data…",
  "Dosya yükleme sırasına eklendi": "Added to the upload queue",
  "Derin Düşünme (CoT)": "Deep Reasoning (CoT)",
  "Canlı Web Araştırması": "Live Web Research",
  "Canlı Veri": "Live Data",
  "İletişim Kanalı:": "Channel:",
  "FastAPI WS Link (Live)": "FastAPI WS link (live)",
  "Anlık Klinik Bağlam": "Live Clinical Context",
  "Tansiyon": "Blood Pressure",
  "Oksijen (SpO2)": "Oxygen (SpO2)",
  "Sıcaklık": "Temperature",
  "Göz Basıncı (IOP)": "Eye Pressure (IOP)",
  "Stres (Kortizol)": "Stress (Cortisol)",
  "* Asistan, mesajlarınızı yanıtlarken yukarıda yer alan telemetri verilerini tıbbi karar mekanizmalarına RAG ile dahil eder.":
    "* When answering, the assistant feeds the telemetry above into its clinical reasoning through RAG.",
  "Sinyal bekleniyor...": "Waiting for signal…",
  "Sil": "Delete",
  "Fotoğraf/Video Yükle": "Upload photo/video",
  "Klinik hekime sorunuzu yazın...": "Ask the clinical assistant…",
  "KAREYİ": "OPEN",
  "aç": "the frame",

  "KAYIT · SAĞLIK PROFİLİ": "RECORD · HEALTH PROFILE",
  "KAN": "BLOOD",
  "KRONİK": "CHRONIC",
  "ALERJİ": "ALLERGY",
  "İLAÇ": "MEDICATION",
  "Yaş": "Age",
  "PROFİLİ KAYDET": "SAVE PROFILE",
  "Muayeneler": "Visits",
  "Reçeteler": "Prescriptions",
  "Laboratuvar": "Lab Results",
  "Yapay Zeka Çözümlüyor...": "AI is parsing…",
  "Dosyayı Seçin veya Sürükleyin": "Choose or drop a file",
  "Zayıf": "Underweight",
  "Normal (Sağlıklı)": "Normal (healthy)",
  "Fazla Kilolu": "Overweight",
  "Obezite": "Obese",

  "KAM 03 · TESPİT": "CAM 03 · DETECT",
  "Bir nesne yazın ve Tespit Et'e tıklayın": "Type an object and press Detect",
  "nesne tespit edildi": "objects detected",

  "Yükseliyor ↑": "Rising ↑",
  "Düşüyor ↓": "Falling ↓",
  "Sabit →": "Stable →",
  "/dk": "/min",

  // ── Kimlik ekranı ──
  "ArgusLens · Operatör konsolu": "ArgusLens · Operator console",
  "Telefonla giriş": "Sign in by phone",
  "Konsola gir": "Enter the console",
  "Hesap aç": "Create an account",
  "Numaranıza gönderilen kodu girin.": "Enter the code sent to your number.",
  "Google, Apple, e-posta veya telefon ile.": "With Google, Apple, email or phone.",
  "Kimlik yöntemi": "Sign-in method",
  "Giriş yap": "Sign in",
  "Kayıt ol": "Register",
  "veya": "or",
  "E-posta, telefon veya kullanıcı adı": "Email, phone or username",
  "Parola": "Password",
  "Doğrulama kodu": "Verification code",
  "Telefona kod gönder": "Send a code to my phone",
  "Kayıt yöntemi": "Registration method",
  "E-posta": "Email",
  "E-posta adresi": "Email address",
  "Telefon numarası": "Phone number",
  "En az 8 karakter, harf ve rakam içermeli.":
    "At least 8 characters, with letters and digits.",
  "Sağlık verilerimin klinik karar desteği amacıyla işlenmesine ilişkin aydınlatma metnini okudum ve onaylıyorum.":
    "I have read and accept the privacy notice covering the processing of my health data for clinical decision support.",
  "Hesabı oluştur": "Create account",
  "Kod gönder": "Send code",
  "Parolayı gizle": "Hide password",
  "Parolayı göster": "Show password",
  "Google ile devam et": "Continue with Google",
  "Apple ile devam et": "Continue with Apple",
  "Google bekleniyor…": "Waiting for Google…",
  "Apple bekleniyor…": "Waiting for Apple…",
  "Sunucuya ulaşılamadı. Backend çalışıyor mu?":
    "Could not reach the server. Is the backend running?",
  "Sosyal giriş başarısız.": "Social sign-in failed.",
  "Kullanıcı adı/e-posta ve parola gerekli.": "Username/email and password are required.",
  "Giriş başarısız.": "Sign-in failed.",
  "Devam etmek için aydınlatma metnini onaylayın.": "Accept the privacy notice to continue.",
  "Kayıt tamamlanamadı.": "Registration could not be completed.",
  "Kod telefonunuza gönderildi.": "A code has been sent to your phone.",
  "Kod gönderilemedi.": "The code could not be sent.",
  "Kod doğrulanamadı.": "The code could not be verified.",
  "Google kimlik token'ı alınamadı.": "Could not obtain a Google ID token.",
  "Google oturum açma kitaplığı yüklenemedi.":
    "The Google sign-in library could not be loaded.",
  "Apple oturum açma kitaplığı yüklenemedi.":
    "The Apple sign-in library could not be loaded.",
  "Google oturum açma henüz hazır değil.": "Google sign-in is not ready yet.",
  "Tarayıcıda açık bir Google oturumu yok. Google hesabınıza girip tekrar deneyin.":
    "No Google session is open in this browser. Sign in to your Google account and try again.",
  "Google penceresi açılamadı. Üçüncü taraf çerezleri engelleniyor olabilir.":
    "The Google window could not open. Third-party cookies may be blocked.",
  "Apple oturum açma henüz hazır değil.": "Apple sign-in is not ready yet.",
  "Apple kimlik token'ı alınamadı.": "Could not obtain an Apple ID token.",
  "Apple ile giriş iptal edildi.": "Apple sign-in was cancelled.",
  "Sunucuda GOOGLE_CLIENT_ID tanımlı değil": "GOOGLE_CLIENT_ID is not set on the server",
  "Sunucuda APPLE_CLIENT_ID tanımlı değil": "APPLE_CLIENT_ID is not set on the server",
  "Google ve Apple girişleri yapılandırılmadı.":
    "Google and Apple sign-in are not configured.",
  "Google girişi yapılandırılmadı.": "Google sign-in is not configured.",
  "Apple girişi yapılandırılmadı.": "Apple sign-in is not configured.",
  // ── Asistan: karşılama ve hazır sorular ──
  "Merhaba! Ben ArgusLens Biyonik Lens klinik asistanıyım. Sağlığınız, anlık vital değerleriniz veya tıbbi sorularınız hakkında benimle konuşabilirsiniz. Size nasıl yardımcı olabilirim?":
    "Hello. I'm the ArgusLens bionic lens clinical assistant. You can talk to me about your health, your live vitals or any medical question. How can I help?",
  "🔍 Vital Durumumu Yorumla":
    "🔍 Interpret my vitals",
  "Şu anki vital değerlerimi analiz edip bana genel sağlık raporumu açıklar mısın?":
    "Could you analyse my current vitals and explain my overall health report?",
  "⚠️ NEWS2 Risk Raporu":
    "⚠️ NEWS2 risk report",
  "NEWS2 skorum kaç ve bu tıbbi olarak ne anlama geliyor? Risk altında mıyım?":
    "What is my NEWS2 score, what does it mean clinically, and am I at risk?",
  "💡 Stres & Göz Basıncı Tavsiyesi":
    "💡 Stress & eye pressure advice",
  "Stres seviyem ve göz içi basıncım (IOP) ne durumda? Bunları kontrol altında tutmak için ne önerirsin?":
    "How are my stress level and intraocular pressure (IOP)? What do you suggest to keep them under control?",
  "E-posta veya telefon ile devam edin.": "Continue with email or phone.",

  "AI Risk Seviyesi:": "AI risk level:",
  "Stabil": "Stable",

  "Düşük Riskli": "Low risk",
  "Orta Riskli": "Moderate risk",
  "Yüksek Risk / Kritik": "High risk / critical",

  // ── Ortak ──
  "Geri": "Back",
  "Kaydet": "Save",
  "Yükleniyor": "Loading",
};

/**
 * Yüzde biçimi dile göre değişir: Türkçe'de işaret önde (%60),
 * İngilizce'de arkada (60%).
 */
export function pct(value: number | string, locale: Locale): string {
  return locale === "en" ? `${value}%` : `%${value}`;
}

/* ── Depo ────────────────────────────────────────────────────────────────────
   Seçim React state'inde değil, modül düzeyinde bir dış depoda tutulur ve
   `useSyncExternalStore` ile okunur.

   Sebep: tercih localStorage'da, yani React'in dışında. Efekt içinde
   setState ile okumak zincirleme render tetikler (React Compiler bunu hata
   sayıyor) ve sunucu/istemci render'ı arasında bir kare Türkçe yanıp söner.
   Dış depoda `getServerSnapshot` sunucuya "tr" derken istemci ilk render'da
   kayıtlı değeri okur — hydration uyuşmazlığı olmadan.

   Aynı sekmedeki tüm tüketiciler tek abonelikten beslenir; `storage` olayı
   sayesinde ikinci bir sekmede yapılan seçim de anında yansır.
   ────────────────────────────────────────────────────────────────────────── */

let current: Locale = "tr";
const listeners = new Set<() => void>();

function readStored(): Locale {
  const saved = window.localStorage.getItem(STORAGE_KEY);
  return saved === "en" ? "en" : "tr";
}

function subscribe(cb: () => void) {
  if (listeners.size === 0) {
    current = readStored();
    document.documentElement.lang = current;
  }
  listeners.add(cb);

  const onStorage = (e: StorageEvent) => {
    if (e.key !== STORAGE_KEY) return;
    current = readStored();
    document.documentElement.lang = current;
    listeners.forEach((l) => l());
  };
  window.addEventListener("storage", onStorage);

  return () => {
    listeners.delete(cb);
    window.removeEventListener("storage", onStorage);
  };
}

const getSnapshot = () => current;
const getServerSnapshot = (): Locale => "tr";

function writeLocale(l: Locale) {
  if (l === current) return;
  current = l;
  window.localStorage.setItem(STORAGE_KEY, l);
  document.documentElement.lang = l;
  listeners.forEach((cb) => cb());
}

type Ctx = {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (tr: string) => string;
};

const LocaleCtx = createContext<Ctx>({
  locale: "tr",
  setLocale: () => {},
  t: (tr) => tr,
});

export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const locale = useSyncExternalStore(
    subscribe,
    getSnapshot,
    getServerSnapshot
  );

  const value = useMemo<Ctx>(
    () => ({
      locale,
      setLocale: writeLocale,
      t: (tr: string) => (locale === "en" ? (EN[tr] ?? tr) : tr),
    }),
    [locale]
  );

  return <LocaleCtx.Provider value={value}>{children}</LocaleCtx.Provider>;
}

export function useLocale() {
  return useContext(LocaleCtx);
}

/** Kısa yol: yalnız çeviri fonksiyonu gerektiğinde. */
export function useT() {
  return useContext(LocaleCtx).t;
}
