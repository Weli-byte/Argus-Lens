from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.session import get_db
from models.domain import HealthProfile, User
from pydantic import BaseModel
from typing import List, Optional
import os
import io
import pypdf
import datetime
import json
import logging
from openai import AsyncOpenAI

router = APIRouter(prefix="/profile", tags=["profile"])
logger = logging.getLogger(__name__)

class ProfileUpdate(BaseModel):
    age: int
    height: float
    weight: float
    blood_type: str
    gender: str
    chronic_diseases: List[str]
    allergies: List[str]
    active_medications: List[str]
    iop_calibration: float
    glucose_calibration: float
    daily_water_intake: Optional[int] = 0
    # Hastane idari kaydi: kimlik, sigorta, acil yakini, hekim, yasam tarzi.
    # Tek JSON alani -> semaya her yeni alan icin sutun eklemek gerekmiyor.
    admin_record: Optional[dict] = None

class WaterUpdate(BaseModel):
    amount: int

async def get_fallback_profile() -> dict:
    profile_path = os.path.join(os.getcwd(), "chats", "profile.json")
    os.makedirs(os.path.dirname(profile_path), exist_ok=True)
    
    if os.path.exists(profile_path):
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
            
    # Default fallback data
    default_profile = {
        "age": 28,
        "height": 178.0,
        "weight": 74.5,
        "blood_type": "A Rh+",
        "gender": "Erkek",
        "chronic_diseases": ["Hipertansiyon", "Diyabet"],
        "allergies": ["Penisilin", "Polen"],
        "active_medications": ["Co-Diovan 160mg", "Glifor 1000mg"],
        "iop_calibration": 15.0,
        "glucose_calibration": 1.0,
        "daily_water_intake": 1250,
        "admin_record": {
            "protocol_no": "ARG-2026-004182",
            "full_name": "",
            "birth_date": "",
            "phone": "",
            "insurance_provider": "SGK",
            "insurance_no": "",
            "emergency_name": "",
            "emergency_relation": "",
            "emergency_phone": "",
            "primary_physician": "Dr. Canan Dağdeviren",
            "clinic": "Kardiyoloji",
            "smoking": "Hiç kullanmadı",
            "alcohol": "Nadiren",
            "organ_donor": False,
            "family_history": ["Hipertansiyon (baba)", "Tip 2 diyabet (anne)"],
            "vaccinations": ["Hepatit B (3 doz)", "Tetanoz (2024)"]
        },
        "visit_history": [
            {"date": "2026-06-12", "dept": "Kardiyoloji", "doctor": "Dr. Canan Dağdeviren", "diagnosis": "Esansiyel Hipertansiyon (Kontrol)"},
            {"date": "2026-05-18", "dept": "Göz Hastalıkları", "doctor": "Dr. Mehmet Öz", "diagnosis": "Glokom Şüphesi / IOP Takibi"},
            {"date": "2026-04-05", "dept": "Dahiliye (Endokrinoloji)", "doctor": "Dr. Gazi Yaşargil", "diagnosis": "Tip 2 Diyabet (Başlangıç Evresi)"}
        ],
        "prescriptions": [
            {"date": "2026-06-12", "doctor": "Dr. Canan Dağdeviren", "meds": ["Co-Diovan 160mg (1x1)", "Vasilip 20mg (1x1)"]},
            {"date": "2026-05-18", "doctor": "Dr. Mehmet Öz", "meds": ["Cosopt Göz Damlası (2x1)"]},
            {"date": "2026-04-05", "doctor": "Dr. Gazi Yaşargil", "meds": ["Glifor 1000mg (2x1)"]}
        ],
        "lab_results": [
            {"date": "2026-06-12", "test": "Göz İçi Basıncı (IOP)", "value": "18.5 mmHg", "status": "Normal"},
            {"date": "2026-04-05", "test": "Açlık Kan Şekeri (Glikoz)", "value": "112 mg/dL", "status": "Yüksek"},
            {"date": "2026-04-05", "test": "HbA1c (Glukozile Hemoglobin)", "value": "%5.9", "status": "Pre-Diyabet"},
            {"date": "2026-04-05", "test": "Total Kolesterol", "value": "210 mg/dL", "status": "Hafif Yüksek"}
        ]
    }
    
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(default_profile, f, ensure_ascii=False, indent=2)
        
    return default_profile

async def save_fallback_profile(data: dict):
    profile_path = os.path.join(os.getcwd(), "chats", "profile.json")
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@router.get("")
async def get_profile(db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(HealthProfile))
        profile = result.scalars().first()
        
        if not profile:
            user_result = await db.execute(select(User))
            user = user_result.scalars().first()
            user_id = user.id if user else None
            
            profile = HealthProfile(
                user_id=user_id,
                age=28,
                height=178.0,
                weight=74.5,
                blood_type="A Rh+",
                gender="Erkek",
                chronic_diseases=["Hipertansiyon", "Diyabet"],
                allergies=["Penisilin", "Polen"],
                active_medications=["Co-Diovan 160mg", "Glifor 1000mg"],
                iop_calibration=15.0,
                glucose_calibration=1.0,
                daily_water_intake=1250
            )
            db.add(profile)
            await db.commit()
            await db.refresh(profile)
            
        return profile
    except Exception as e:
        logger.warning(f"Database error in get_profile, falling back to JSON: {e}")
        return await get_fallback_profile()

@router.post("")
async def update_profile(update_data: ProfileUpdate, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(HealthProfile))
        profile = result.scalars().first()
        
        if not profile:
            user_result = await db.execute(select(User))
            user = user_result.scalars().first()
            user_id = user.id if user else None
            profile = HealthProfile(user_id=user_id)
            db.add(profile)
            
        profile.age = update_data.age
        profile.height = update_data.height
        profile.weight = update_data.weight
        profile.blood_type = update_data.blood_type
        profile.gender = update_data.gender
        profile.chronic_diseases = update_data.chronic_diseases
        profile.allergies = update_data.allergies
        profile.active_medications = update_data.active_medications
        if update_data.admin_record is not None and hasattr(profile, "admin_record"):
            profile.admin_record = update_data.admin_record
        profile.iop_calibration = update_data.iop_calibration
        profile.glucose_calibration = update_data.glucose_calibration
        if update_data.daily_water_intake is not None:
            profile.daily_water_intake = update_data.daily_water_intake
            
        await db.commit()
        await db.refresh(profile)
        return profile
    except Exception as e:
        logger.warning(f"Database error in update_profile, falling back to JSON: {e}")
        fallback = await get_fallback_profile()
        fallback["age"] = update_data.age
        fallback["height"] = update_data.height
        fallback["weight"] = update_data.weight
        fallback["blood_type"] = update_data.blood_type
        fallback["gender"] = update_data.gender
        fallback["chronic_diseases"] = update_data.chronic_diseases
        fallback["allergies"] = update_data.allergies
        fallback["active_medications"] = update_data.active_medications
        fallback["iop_calibration"] = update_data.iop_calibration
        fallback["glucose_calibration"] = update_data.glucose_calibration
        if update_data.admin_record is not None:
            # Yedek dal bu alani yazmiyordu; hastane kunyesi her kayitta
            # sessizce kayboluyordu.
            fallback["admin_record"] = update_data.admin_record
        if update_data.daily_water_intake is not None:
            fallback["daily_water_intake"] = update_data.daily_water_intake
        await save_fallback_profile(fallback)
        return fallback

@router.post("/water")
async def update_water(request: WaterUpdate, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(HealthProfile))
        profile = result.scalars().first()
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
            
        profile.daily_water_intake += request.amount
        await db.commit()
        await db.refresh(profile)
        return {"status": "success", "daily_water_intake": profile.daily_water_intake}
    except Exception as e:
        logger.warning(f"Database error in update_water, falling back to JSON: {e}")
        fallback = await get_fallback_profile()
        fallback["daily_water_intake"] = fallback.get("daily_water_intake", 0) + request.amount
        await save_fallback_profile(fallback)
        return {"status": "success", "daily_water_intake": fallback["daily_water_intake"]}

@router.post("/generate-report")
async def generate_clinic_report(db: AsyncSession = Depends(get_db)):
    # Load profile details (either db or json fallback)
    age = 28
    gender = "Erkek"
    height = 178.0
    weight = 74.5
    blood_type = "A Rh+"
    chronic_diseases = ["Hipertansiyon", "Diyabet"]
    allergies = ["Penisilin"]
    active_medications = ["Co-Diovan 160mg", "Glifor 1000mg"]
    visit_history = []
    prescriptions = []
    lab_results = []

    try:
        result = await db.execute(select(HealthProfile))
        profile = result.scalars().first()
        if profile:
            age = profile.age
            gender = profile.gender
            height = profile.height
            weight = profile.weight
            blood_type = profile.blood_type
            chronic_diseases = profile.chronic_diseases
            allergies = profile.allergies
            active_medications = profile.active_medications
            visit_history = profile.visit_history
            prescriptions = profile.prescriptions
            lab_results = profile.lab_results
        else:
            fallback = await get_fallback_profile()
            age = fallback["age"]
            gender = fallback["gender"]
            height = fallback["height"]
            weight = fallback["weight"]
            blood_type = fallback["blood_type"]
            chronic_diseases = fallback["chronic_diseases"]
            allergies = fallback["allergies"]
            active_medications = fallback["active_medications"]
            visit_history = fallback["visit_history"]
            prescriptions = fallback["prescriptions"]
            lab_results = fallback["lab_results"]
    except Exception as e:
        logger.warning(f"Database error in generate_clinic_report, falling back to JSON: {e}")
        fallback = await get_fallback_profile()
        age = fallback["age"]
        gender = fallback["gender"]
        height = fallback["height"]
        weight = fallback["weight"]
        blood_type = fallback["blood_type"]
        chronic_diseases = fallback["chronic_diseases"]
        allergies = fallback["allergies"]
        active_medications = fallback["active_medications"]
        visit_history = fallback["visit_history"]
        prescriptions = fallback["prescriptions"]
        lab_results = fallback["lab_results"]
        
    import redis.asyncio as aioredis
    from core.config import settings
    
    heart_rate = 74
    bp = "120/80"
    spo2 = 98.5
    temp = 36.6
    news2_score = 0
    
    try:
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True, protocol=2)
        telemetry_raw = await r.get("arguslens:vitals:latest")
        if telemetry_raw:
            telemetry = json.loads(telemetry_raw)
            v = telemetry.get("vitals", {})
            n = telemetry.get("news2", {})
            heart_rate = v.get("heart_rate", heart_rate)
            bp = f"{v.get('systolic_bp', 120)}/{v.get('diastolic_bp', 80)}"
            spo2 = v.get("spo2", spo2)
            temp = v.get("temperature", temp)
            news2_score = n.get("score", news2_score)
    except Exception as e:
        logger.warning(f"Could not fetch live telemetry for AI report: {e}")

    system_prompt = (
        "Sen saygın bir hastanede çalışan uzman klinik hekimsin. Görevin, hastanın ArgusLens biyonik lensinden "
        "alınan güncel vital verileri, kronik hastalıkları, alerjileri, kullandığı ilaçları ve E-Nabız geçmişini "
        "kullanarak profesyonel bir 'Klinik Epikriz ve Sağlık Özet Raporu' oluşturmaktır.\n\n"
        "Rapor dili resmi, klinik, detaylı ve hekimlerin okuyabileceği profesyonellikte (epikriz formatında) olmalıdır. "
        "Markdown kullanarak başlıklar, listeler ve tablolar ile raporu şık bir şekilde yapılandır."
    )
    
    user_prompt = (
        f"HASTA PROFİLİ:\n"
        f"- Yaş: {age}\n"
        f"- Cinsiyet: {gender}\n"
        f"- Boy: {height} cm | Kilo: {weight} kg\n"
        f"- Kan Grubu: {blood_type}\n"
        f"- Kronik Hastalıklar: {', '.join(chronic_diseases) if chronic_diseases else 'Bulunmuyor'}\n"
        f"- Alerjiler: {', '.join(allergies) if allergies else 'Bulunmuyor'}\n"
        f"- Aktif İlaçlar: {', '.join(active_medications) if active_medications else 'Bulunmuyor'}\n\n"
        f"GÜNCEL TELEMETRİ BULGULARI:\n"
        f"- Nabız: {heart_rate} bpm\n"
        f"- Tansiyon: {bp} mmHg\n"
        f"- Oksijen (SpO2): %{spo2}\n"
        f"- Vücut Sıcaklığı: {temp} °C\n"
        f"- NEWS2 Skoru: {news2_score}/21\n\n"
        f"E-NABIZ MEDİKAL GEÇMİŞİ:\n"
        f"- Son Muayeneler: {visit_history}\n"
        f"- Reçeteler: {prescriptions}\n"
        f"- Son Laboratuvar Bulguları: {lab_results}\n\n"
        f"Lütfen bu verileri klinik olarak değerlendirip, hastanın mevcut durumu, ilaç uyumu ve "
        f"kontrol muayene önerilerini içeren resmi bir hekim epikriz raporu oluştur."
    )
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {
            "report": (
                f"# KLİNİK EPİKRİZ VE SAĞLIK ÖZET RAPORU\n"
                f"**Rapor Tarihi:** {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                f"## 1. HASTA DEMOGRAFİSİ & BULGULAR\n"
                f"*   **Yaş/Cinsiyet:** {age} / {gender}\n"
                f"*   **Kan Grubu:** {blood_type}\n"
                f"*   **Mevcut Vital Değerler:** Nabız: {heart_rate} bpm, Tansiyon: {bp} mmHg, SpO2: %{spo2}, Sıcaklık: {temp}°C.\n"
                f"*   **NEWS2 Skoru:** {news2_score} (Düşük Risk)\n\n"
                f"## 2. KRONİK PATOLOJİLER & İLAÇ KULLANIMI\n"
                f"Hastanın özgeçmişinde yer alan kronik hastalıkları ({', '.join(chronic_diseases) if chronic_diseases else 'Yok'}) ve "
                f"aktif olarak kullandığı ilaçlar ({', '.join(active_medications) if active_medications else 'Yok'}) incelenmiştir.\n\n"
                f"## 3. HEKİM DEĞERLENDİRME NOTU (DEMO)\n"
                f"OpenAI API Anahtarı girilmediği için bu rapor **demo modunda** simüle edilmiştir. "
                f"Hastanın vital bulguları stabildir, acil bir müdahale endikasyonu bulunmamaktadır. "
                f"Düzenli kardiyoloji ve endokrinoloji kontrollerinin aksatılmaması önerilir."
            )
        }
        
    try:
        client = AsyncOpenAI(api_key=api_key)
        completion = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=1500
        )
        report_text = completion.choices[0].message.content or ""
        return {"report": report_text}
    except Exception as e:
        logger.error(f"Failed to generate AI clinic report: {e}")
        return {"error": f"Rapor oluşturulamadı: {str(e)}"}

@router.post("/upload-enabiz")
async def upload_enabiz(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    content_type = file.content_type or ""
    filename = file.filename or ""
    extracted_text = ""
    
    try:
        file_bytes = await file.read()
        
        if filename.endswith(".pdf") or "pdf" in content_type:
            pdf_file = io.BytesIO(file_bytes)
            reader = pypdf.PdfReader(pdf_file)
            text_parts = []
            for page in reader.pages:
                text_parts.append(page.extract_text() or "")
            extracted_text = "\n".join(text_parts)
        else:
            extracted_text = file_bytes.decode("utf-8", errors="ignore")
            
    except Exception as e:
        logger.error(f"Failed to read/parse uploaded E-Nabız file: {e}")
        raise HTTPException(status_code=400, detail=f"Dosya okunamadı: {str(e)}")
        
    if not extracted_text.strip():
        raise HTTPException(status_code=400, detail="Dosya içeriği boş veya okunabilir metin bulunamadı.")
        
    trimmed_text = extracted_text[:12000]
    
    system_prompt = (
        "Sen bir E-Nabız tıbbi doküman analiz uzmanısın. Sana sunulan ham E-Nabız dosya metnini (muayene geçmişi, reçeteler, laboratuvar testleri) analiz etmeli ve bulduğun tüm verileri tam olarak şu JSON şemasında çıkarmalısın:\n"
        "{\n"
        "  \"visit_history\": [{\"date\": \"YYYY-MM-DD\", \"dept\": \"Tıbbi Bölüm\", \"doctor\": \"Dr. İsim Soyisim\", \"diagnosis\": \"Klinik Teşhis/Tanı\"}],\n"
        "  \"prescriptions\": [{\"date\": \"YYYY-MM-DD\", \"doctor\": \"Dr. İsim Soyisim\", \"meds\": [\"İlaç Adı ve Dozu\"]}],\n"
        "  \"lab_results\": [{\"date\": \"YYYY-MM-DD\", \"test\": \"Tahlil/Test Adı\", \"value\": \"Bulgu Değeri (örn. 112 mg/dL)\", \"status\": \"Normal/Yüksek/Düşük referans durumu\"}]\n"
        "}\n\n"
        "KURALLAR:\n"
        "1. Çıktı sadece ve sadece geçerli bir JSON objesi olmalıdır. Markdown, ```json ... ``` etiketleri veya herhangi bir açıklama metni kesinlikle İÇERMEMELİDİR. Doğrudan süslü parantez ile başlayıp bitmelidir.\n"
        "2. Eğer belgede reçete veya test bulamazsan boş liste (`[]`) dön.\n"
        "3. Tarih formatı YYYY-MM-DD olmalıdır (örn. '2026-06-12'). Eğer sadece yıl veya ay varsa uygun tahmini tarihi yaz.\n"
        "4. Tıbbi departman ve hekim isimlerini düzgünce baş harfleri büyük şekilde çıkar."
    )
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OpenAI API Anahtarı (.env) tanımlı değil.")
        
    try:
        client = AsyncOpenAI(api_key=api_key)
        completion = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"E-NABIZ DOSYA METNİ:\n\n{trimmed_text}"}
            ],
            temperature=0.2,
            max_tokens=2000
        )
        
        raw_response = completion.choices[0].message.content or ""
        cleaned_response = raw_response.strip()
        if cleaned_response.startswith("```json"):
            cleaned_response = cleaned_response[7:]
        if cleaned_response.endswith("```"):
            cleaned_response = cleaned_response[:-3]
        cleaned_response = cleaned_response.strip()
        
        parsed_data = json.loads(cleaned_response)
        
        visit_history = parsed_data.get("visit_history", [])
        prescriptions = parsed_data.get("prescriptions", [])
        lab_results = parsed_data.get("lab_results", [])
        
        try:
            result = await db.execute(select(HealthProfile))
            profile = result.scalars().first()
            if profile:
                profile.visit_history = visit_history
                profile.prescriptions = prescriptions
                profile.lab_results = lab_results
                await db.commit()
                await db.refresh(profile)
                return profile
            else:
                fallback = await get_fallback_profile()
                fallback["visit_history"] = visit_history
                fallback["prescriptions"] = prescriptions
                fallback["lab_results"] = lab_results
                await save_fallback_profile(fallback)
                return fallback
        except Exception as db_err:
            logger.warning(f"Database error saving E-Nabız parsed records, falling back to JSON: {db_err}")
            fallback = await get_fallback_profile()
            fallback["visit_history"] = visit_history
            fallback["prescriptions"] = prescriptions
            fallback["lab_results"] = lab_results
            await save_fallback_profile(fallback)
            return fallback
            
    except json.JSONDecodeError as json_err:
        logger.error(f"Failed to parse GPT-4o response as JSON: {json_err}. Response: {raw_response}")
        raise HTTPException(status_code=500, detail="Yapay zeka analiz çıktısı geçerli bir JSON şemasına dönüştürülemedi.")
    except Exception as e:
        logger.error(f"E-Nabız AI parsing execution error: {e}")
        raise HTTPException(status_code=500, detail=f"Dosya analizi sırasında hata: {str(e)}")

