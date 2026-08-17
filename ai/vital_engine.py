import os
import time
import random
import logging
import asyncio
from typing import Dict, Any, List
import numpy as np
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# NEWS2 Scoring Constants
class NEWS2Calculator:
    @staticmethod
    def calculate(
        heart_rate: float,
        systolic_bp: float,
        spo2: float,
        temp: float,
        resp_rate: float,
        alert: bool = True
    ) -> Dict[str, Any]:
        """
        Calculate NEWS2 (National Early Warning Score 2) from vital signs.
        """
        score = 0
        details = {}

        # 1. Respiration Rate (bpm)
        rr_score = 0
        if resp_rate <= 8:
            rr_score = 3
        elif 9 <= resp_rate <= 11:
            rr_score = 1
        elif 12 <= resp_rate <= 20:
            rr_score = 0
        elif 21 <= resp_rate <= 24:
            rr_score = 2
        elif resp_rate >= 25:
            rr_score = 3
        score += rr_score
        details["respiratory_rate"] = rr_score

        # 2. SpO2 Scale 1 (%)
        spo2_score = 0
        if spo2 <= 91:
            spo2_score = 3
        elif 92 <= spo2 <= 93:
            spo2_score = 2
        elif 94 <= spo2 <= 95:
            spo2_score = 1
        elif spo2 >= 96:
            spo2_score = 0
        score += spo2_score
        details["spo2"] = spo2_score

        # 3. Systolic Blood Pressure (mmHg)
        sbp_score = 0
        if systolic_bp <= 90:
            sbp_score = 3
        elif 91 <= systolic_bp <= 100:
            sbp_score = 2
        elif 101 <= systolic_bp <= 110:
            sbp_score = 1
        elif 111 <= systolic_bp <= 219:
            sbp_score = 0
        elif systolic_bp >= 220:
            sbp_score = 3
        score += sbp_score
        details["systolic_bp"] = sbp_score

        # 4. Heart Rate (bpm)
        hr_score = 0
        if heart_rate <= 40:
            hr_score = 3
        elif 41 <= heart_rate <= 50:
            hr_score = 1
        elif 51 <= heart_rate <= 90:
            hr_score = 0
        elif 91 <= heart_rate <= 110:
            hr_score = 1
        elif 111 <= heart_rate <= 130:
            hr_score = 2
        elif heart_rate >= 131:
            hr_score = 3
        score += hr_score
        details["heart_rate"] = hr_score

        # 5. Temperature (°C)
        temp_score = 0
        if temp <= 35.0:
            temp_score = 3
        elif 35.1 <= temp <= 36.0:
            temp_score = 1
        elif 36.1 <= temp <= 38.0:
            temp_score = 0
        elif 38.1 <= temp <= 39.0:
            temp_score = 1
        elif temp >= 39.1:
            temp_score = 2
        score += temp_score
        details["temperature"] = temp_score

        # 6. Consciousness (Alert = 0, CVPU = 3)
        cons_score = 0 if alert else 3
        score += cons_score
        details["consciousness"] = cons_score

        # Determine risk level
        if score == 0:
            level = "SAFE"
            status = "Stabil"
        elif 1 <= score <= 4:
            level = "CAUTION"
            status = "Düşük Riskli"
        elif 5 <= score <= 6:
            level = "WARNING"
            status = "Orta Riskli"
        else:
            level = "DANGER"
            status = "Yüksek Risk / Kritik"

        return {
            "score": score,
            "level": level,
            "status": status,
            "details": details
        }


class PhysiologicalSimulator:
    def __init__(self):
        # Base states for patient simulation
        self.state = "stable"
        self.time_in_state = 0
        
        # Base values
        self.hr = 75.0
        self.sbp = 120.0
        self.dbp = 80.0
        self.spo2 = 98.0
        self.temp = 36.5
        self.rr = 14.0
        self.iop = 15.0
        self.glucose = 85.0
        self.cortisol = 10.0

    def generate_vitals(self) -> Dict[str, Any]:
        """
        Generates realistic physiological time-series data with dependencies.
        Transitions states to simulate stable, hyperactive, septic, or hypotensive conditions.
        """
        # Periodic state transition logic
        self.time_in_state += 1
        if self.time_in_state > 60:  # Change state every ~60 seconds
            self.state = random.choice(["stable", "stable", "fever", "tachycardia", "hypotension"])
            self.time_in_state = 0
            logger.info(f"Physiological state transitioned to: {self.state}")

        # Core simulator loops with correlations
        noise = lambda scale: random.normalvariate(0, scale)

        if self.state == "stable":
            # Normal fluctuation
            self.hr = max(60.0, min(100.0, self.hr + noise(1.0) * 0.5 + (75.0 - self.hr) * 0.05))
            self.temp = max(36.1, min(37.2, self.temp + noise(0.05) + (36.5 - self.temp) * 0.05))
            self.spo2 = max(96.0, min(100.0, self.spo2 + noise(0.2) + (98.5 - self.spo2) * 0.05))
            self.rr = max(12.0, min(18.0, 10 + 0.05 * self.hr + noise(0.5)))
            
            # SBP correlates with Heart Rate
            target_sbp = 90 + 0.4 * self.hr
            self.sbp = max(110.0, min(130.0, self.sbp + noise(1.5) + (target_sbp - self.sbp) * 0.1))
            self.dbp = max(70.0, min(85.0, 0.65 * self.sbp + noise(1.0)))
            
            self.iop = max(12.0, min(18.0, self.iop + noise(0.3) + (15.0 - self.iop) * 0.05))
            self.glucose = max(80.0, min(110.0, self.glucose + noise(1.0) + (90.0 - self.glucose) * 0.05))
            self.cortisol = max(5.0, min(15.0, self.cortisol + noise(0.5) + (10.0 - self.cortisol) * 0.05))

        elif self.state == "fever":
            # High temperature, elevated HR and RR, slight drop in SBP
            self.temp = max(38.2, min(39.8, self.temp + 0.1 + noise(0.05)))
            self.hr = max(90.0, min(120.0, self.hr + 1.0 + noise(1.0) + (105.0 - self.hr) * 0.05))
            self.rr = max(18.0, min(24.0, 12 + 0.08 * self.hr + noise(0.5)))
            self.spo2 = max(94.0, min(97.0, self.spo2 + noise(0.3) + (95.5 - self.spo2) * 0.05))
            self.sbp = max(100.0, min(115.0, self.sbp - 0.5 + noise(1.5)))
            self.dbp = max(60.0, min(75.0, 0.62 * self.sbp + noise(1.0)))
            self.cortisol = max(18.0, min(28.0, self.cortisol + 0.5 + noise(0.5)))
            self.iop = max(14.0, min(20.0, self.iop + noise(0.3)))
            self.glucose = max(110.0, min(140.0, self.glucose + noise(1.5)))

        elif self.state == "tachycardia":
            # Rapid heart rate, elevated blood pressure, spike in stress/cortisol
            self.hr = max(110.0, min(145.0, self.hr + 2.0 + noise(1.5) + (125.0 - self.hr) * 0.05))
            self.sbp = max(135.0, min(165.0, self.sbp + 2.0 + noise(2.0) + (150.0 - self.sbp) * 0.05))
            self.dbp = max(85.0, min(100.0, 0.65 * self.sbp + noise(1.5)))
            self.rr = max(18.0, min(26.0, 10 + 0.1 * self.hr + noise(0.5)))
            self.spo2 = max(95.0, min(99.0, self.spo2 + noise(0.2)))
            self.temp = max(36.4, min(37.5, self.temp + noise(0.05)))
            self.cortisol = max(22.0, min(35.0, self.cortisol + 1.0 + noise(1.0)))
            self.iop = max(16.0, min(23.0, self.iop + 0.4 + noise(0.3)))
            self.glucose = max(95.0, min(130.0, self.glucose + noise(1.0)))

        elif self.state == "hypotension":
            # Low blood pressure, cold temperature, dropping SpO2, elevated HR to compensate
            self.sbp = max(80.0, min(95.0, self.sbp - 2.0 + noise(2.0) + (88.0 - self.sbp) * 0.05))
            self.dbp = max(45.0, min(60.0, 0.6 * self.sbp + noise(1.5)))
            self.hr = max(85.0, min(110.0, self.hr + 1.0 + noise(1.5)))
            self.temp = max(35.2, min(36.1, self.temp - 0.1 + noise(0.05)))
            self.spo2 = max(90.0, min(94.0, self.spo2 - 0.2 + noise(0.4)))
            self.rr = max(16.0, min(22.0, self.rr + noise(0.5)))
            self.cortisol = max(15.0, min(25.0, self.cortisol + noise(0.5)))
            self.iop = max(9.0, min(14.0, self.iop - 0.3 + noise(0.3)))
            self.glucose = max(65.0, min(80.0, self.glucose - 1.0 + noise(1.0)))

        # Round values to logical precision
        return {
            "heart_rate": round(self.hr, 1),
            "systolic_bp": round(self.sbp, 1),
            "diastolic_bp": round(self.dbp, 1),
            "spo2": round(self.spo2, 1),
            "temperature": round(self.temp, 2),
            "respiratory_rate": round(self.rr, 1),
            "eye_pressure": round(self.iop, 1),
            "tear_glucose": round(self.glucose, 1),
            "stress_level": round(self.cortisol, 1),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }


class MedicalReportGenerator:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if self.api_key:
            self.client = AsyncOpenAI(api_key=self.api_key)
            logger.info("OpenAI Client initialised for GPT-4o report generator.")
        else:
            self.client = None
            logger.warning("No OPENAI_API_KEY found, fallback template engine will be used.")

    def _generate_fallback(self, vitals: Dict[str, Any], news2: Dict[str, Any]) -> Dict[str, str]:
        """
        A robust local rule-based system generating clean, comprehensive Turkish medical reports.
        """
        score = news2["score"]
        level = news2["level"]
        status = news2["status"]
        
        hr = vitals["heart_rate"]
        sbp = vitals["systolic_bp"]
        dbp = vitals["diastolic_bp"]
        spo2 = vitals["spo2"]
        temp = vitals["temperature"]
        rr = vitals["respiratory_rate"]
        iop = vitals["eye_pressure"]
        gl = vitals["tear_glucose"]
        str_lvl = vitals["stress_level"]

        report = (
            f"Hastanın biyonik kontakt lens üzerinden alınan anlık fizyolojik verileri incelenmiştir.\n\n"
            f"Genel Değerlendirme:\n"
            f"Klinik risk değerlendirmesi NEWS2 (National Early Warning Score 2) standardına göre yapılmış olup, "
            f"hastanın risk skoru {score}/21 olarak belirlenmiştir. Bu skor '{status}' kategorisinde değerlendirilmektedir.\n\n"
        )
        
        recs = []

        if level == "SAFE":
            report += (
                f"Kardiyovasküler sistem bulguları (Nabız: {hr} bpm, Tansiyon: {sbp}/{dbp} mmHg) normal fizyolojik sınırlardadır. "
                f"Oksijenasyon seviyesi (%{spo2}) ve vücut sıcaklığı ({temp}°C) dengelidir. "
                f"Göz içi basıncı ({iop} mmHg) ve gözyaşı glikoz düzeyi ({gl} mg/dL) stabil durumdadır.\n\n"
                f"Hastanın şu aşamada herhangi bir akut klinik risk taşımadığı ve genel durumunun iyi olduğu gözlenmiştir."
            )
            recs = [
                "Günlük optimal hidrasyonun korunması için 2-2.5 litre su tüketilmesi önerilir.",
                "Hafif veya orta şiddetli fiziksel aktivite (yürüyüş) devam ettirilmelidir.",
                "Lens sensör verilerinin rutin aralıklarla izlenmesine devam edilmesi yeterlidir."
            ]
        elif level == "CAUTION":
            report += (
                f"Hastanın vital bulgularında hafif sapmalar gözlenmiştir. Nabız {hr} bpm ve tansiyon {sbp}/{dbp} mmHg seviyesindedir. "
                f"Vücut sıcaklığında hafif bir reaksiyon ({temp}°C) veya SpO2 seviyesinde hafif dalgalanma (%{spo2}) mevcuttur. "
                f"Gözyaşı analizinde stres hormonu (Kortizol: {str_lvl} mcg/dL) hafif yükselme eğilimi göstermektedir."
            )
            recs = [
                "Hastanın dinlenmesi ve stres tetikleyici etkenlerden uzak kalması önerilir.",
                "Vital bulguların 4-6 saatlik periyotlarla izlenmesi uygundur.",
                "Eğer semptomlar (baş ağrısı, hafif halsizlik vb.) gelişirse dinlenme süresi artırılmalıdır."
            ]
        elif level == "WARNING":
            report += (
                f"Hastanın vital bulguları orta düzeyde klinik düzensizlik göstermektedir (NEWS2: {score}). "
                f"Özellikle nabız ({hr} bpm), solunum hızı ({rr} breaths/min) ve vücut sıcaklığındaki ({temp}°C) yükseliş "
                f"akut bir enfeksiyon, inflamasyon veya subfebril reaksiyon belirtisi olabilir. "
                f"Göz içi basıncı ({iop} mmHg) üst sınırda yer almaktadır."
            )
            recs = [
                "Hastanın genel klinik durumunun bir tıp uzmanı tarafından değerlendirilmesi önerilir.",
                "Vital değer takibinin 1 saatlik periyotlarla daha sıkı bir şekilde yapılması gerekmektedir.",
                "Bol sıvı alımı sağlanmalı ve hasta sıcaklık artışına karşı gözlemlenmelidir."
            ]
        else: # DANGER
            report += (
                f"DİKKAT: Hastanın vital bulguları kritik sınırlardadır! NEWS2 skoru {score} olup acil tıbbi müdahale ihtiyacı doğabilir. "
                f"Tansiyon ({sbp}/{dbp} mmHg) ve oksijen satürasyonu (%{spo2}) kritik düzeyde düşmüş veya nabız ({hr} bpm) "
                f"aşırı yükselerek taşikardi sınırını aşmıştır. Vücut sıcaklığı ({temp}°C) yüksek ateş düzeyindedir."
            )
            recs = [
                "ACİL: En yakın sağlık kuruluşuna veya acil servis departmanına başvurulması kritik önem taşır.",
                "Tıbbi müdahale gelene kadar hastanın yarı oturur veya düz yatar pozisyonda (tansiyona göre) dinlenmesi sağlanmalıdır.",
                "Oksijen seviyesi ve nabız sürekli olarak canlı ekrandan takip edilmeli, veri akışı kesilmemelidir."
            ]

        return {
            "report": report,
            "recommendations": "\n".join([f"• {r}" for r in recs]),
            "model": "rule_based_fallback"
        }

    async def generate_report(self, vitals: Dict[str, Any], news2: Dict[str, Any]) -> Dict[str, str]:
        """
        Generates a comprehensive clinical assessment and medical recommendation list in Turkish using GPT-4o.
        """
        if not self.client:
            return self._generate_fallback(vitals, news2)

        prompt = (
            f"Sen biyonik bir kontakt lensten gelen verileri analiz eden uzman bir yapay zeka kardiyoloğu ve acil tıp uzmanısın.\n"
            f"Hastanın anlık vital ve ocular biyometrik değerleri:\n"
            f"- Nabız: {vitals['heart_rate']} bpm\n"
            f"- Tansiyon (Kan Basıncı): {vitals['systolic_bp']}/{vitals['diastolic_bp']} mmHg\n"
            f"- Oksijen Satürasyonu (SpO2): %{vitals['spo2']}\n"
            f"- Vücut Sıcaklığı: {vitals['temperature']} °C\n"
            f"- Solunum Hızı: {vitals['respiratory_rate']} breaths/min\n"
            f"- Göz İçi Basıncı (IOP): {vitals['eye_pressure']} mmHg\n"
            f"- Gözyaşı Glikozu: {vitals['tear_glucose']} mg/dL\n"
            f"- Stres Seviyesi (Kortizol): {vitals['stress_level']} mcg/dL\n\n"
            f"Klinik Risk Analiz Değerleri (NEWS2 Standardına göre hesaplanmıştır):\n"
            f"- NEWS2 Risk Skoru: {news2['score']}/21\n"
            f"- Risk Seviyesi: {news2['level']}\n"
            f"- Sağlık Durumu: {news2['status']}\n\n"
            f"Senden isteğim, bu değerlere göre hastanın sağlık durumunu detaylı bir şekilde analiz eden, "
            f"olası tıbbi riskleri veya durumları öngören profesyonel bir tıbbi doktor raporu hazırlaman.\n"
            f"Lütfen raporu Türkçe hazırla ve şu iki başlığı içerecek şekilde formatla:\n"
            f"1. Rapor metnini '### KLİNİK DEĞERLENDİRME' başlığı altında uzun, kapsamlı ve profesyonel tıbbi dille yaz.\n"
            f"2. Önerileri '### TIBBİ ÖNERİLER' başlığı altında madde işaretleri (•) kullanarak detaylı bir şekilde sırala.\n"
            f"Tıbbi değerlendirme tamamen gerçekçi olmalı, ezbere mock bilgiler içermemeli ve hastanın anlık değerleriyle %100 uyumlu olmalıdır."
        )

        try:
            # Call OpenAI GPT-4o API asynchronously
            completion = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Sen uzman, profesyonel bir tıp doktorusun. Türkçe dilinde klinik raporlar yazarsın."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1500
            )
            response_text = completion.choices[0].message.content or ""
            
            # Parse response_text into report and recommendations
            parts = response_text.split("### TIBBİ ÖNERİLER")
            report_part = ""
            recs_part = ""
            
            if len(parts) >= 2:
                report_part = parts[0].replace("### KLİNİK DEĞERLENDİRME", "").strip()
                recs_part = parts[1].strip()
            else:
                report_part = response_text.strip()
                recs_part = "• Tıbbi durumun yakından izlenmesi önerilir.\n• Değerlerde bozulma halinde hekime danışınız."

            return {
                "report": report_part,
                "recommendations": recs_part,
                "model": "gpt-4o"
            }
        except Exception as e:
            logger.error("GPT-4o Medical Report generation failed: %s", e)
            return self._generate_fallback(vitals, news2)
