"use client";

import React, { useState, useEffect } from "react";
import { 
  User, ShieldAlert, Heart, Droplet, Plus, Gauge, 
  Activity, Sparkles, Check, Save, RefreshCw, Phone, Zap, Download, Upload 
} from "lucide-react";
import { useVitalStream } from "@/hooks/useVitalStream";
import { motion, AnimatePresence } from "framer-motion";
import ProfileHero from "@/components/vision/ProfileHero";
import RevealBlocks from "@/components/vision/RevealBlocks";
import PatientRecord, {
  type AdminRecord,
} from "@/components/vision/PatientRecord";

interface VisitRecord { date: string; dept: string; doctor: string; diagnosis: string; }
interface PrescriptionRecord { date: string; doctor: string; meds: string[]; }
interface LabRecord { date: string; test: string; value: string; status: string; }

interface ProfileState {
  age: number; height: number; weight: number; blood_type: string; gender: string;
  chronic_diseases: string[]; allergies: string[]; active_medications: string[];
  iop_calibration: number; glucose_calibration: number; daily_water_intake: number;
  visit_history: VisitRecord[]; prescriptions: PrescriptionRecord[]; lab_results: LabRecord[];
  admin_record?: AdminRecord;
}
import { useT } from "@/lib/i18n";

export default function HealthProfilePage() {
  const t = useT();
  useVitalStream();

  const [profile, setProfile] = useState<ProfileState | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState<"visits" | "prescriptions" | "labs">("visits");

  const [newDisease, setNewDisease] = useState("");
  const [newAllergy, setNewAllergy] = useState("");
  const [newMed, setNewMed] = useState("");

  const [aiReport, setAiReport] = useState<string | null>(null);
  const [generatingReport, setGeneratingReport] = useState(false);


  const [uploadingEnabiz, setUploadingEnabiz] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState(false);

  useEffect(() => { fetchProfile(); }, []);

  const fetchProfile = async () => {
    setLoading(true);
    try {
      const res = await fetch("http://127.0.0.1:8090/api/v1/profile");
      if (res.ok) {
        const data = await res.json();
        setProfile(data);
      }
    } catch (err) {
      console.error("Failed to fetch health profile:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveProfile = async () => {
    if (!profile) return;
    setSaving(true);
    try {
      const res = await fetch("http://127.0.0.1:8090/api/v1/profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          age: profile.age, height: profile.height, weight: profile.weight,
          blood_type: profile.blood_type, gender: profile.gender,
          chronic_diseases: profile.chronic_diseases, allergies: profile.allergies,
          active_medications: profile.active_medications,
          iop_calibration: profile.iop_calibration, glucose_calibration: profile.glucose_calibration,
          daily_water_intake: profile.daily_water_intake,
          admin_record: profile.admin_record ?? {}
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setProfile(data);
        alert("Sağlık profiliniz başarıyla güncellendi.");
      }
    } catch (err) {
      console.error("Failed to save profile:", err);
      alert("Hata: Profil kaydedilemedi.");
    } finally {
      setSaving(false);
    }
  };

  const handleAddWater = async (amount: number) => {
    if (!profile) return;
    try {
      const res = await fetch("http://127.0.0.1:8090/api/v1/profile/water", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ amount }),
      });
      if (res.ok) {
        const data = await res.json();
        setProfile(prev => prev ? { ...prev, daily_water_intake: data.daily_water_intake } : null);
      }
    } catch (err) {
      console.error("Failed to log water intake:", err);
    }
  };

  const handleGenerateAIReport = async () => {
    setGeneratingReport(true);
    setAiReport(null);
    try {
      const res = await fetch("http://127.0.0.1:8090/api/v1/profile/generate-report", { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setAiReport(data.report || data.error);
      }
    } catch (err) {
      console.error("Failed to generate AI report:", err);
      setAiReport("Klinik rapor oluşturulurken ağ hatası meydana geldi.");
    } finally {
      setGeneratingReport(false);
    }
  };

  const handleDownloadReport = () => {
    if (!aiReport) return;
    const blob = new Blob([aiReport], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `ArgusLens_Klinik_Rapor_${new Date().toISOString().split('T')[0]}.txt`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadingEnabiz(true); setUploadError(null); setUploadSuccess(false);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("http://127.0.0.1:8090/api/v1/profile/upload-enabiz", {
        method: "POST", body: formData,
      });

      if (res.ok) {
        const data = await res.json();
        setProfile(data);
        setUploadSuccess(true);
        setTimeout(() => setUploadSuccess(false), 4000);
      } else {
        const errData = await res.json();
        setUploadError(errData.detail || "Dosya yüklenirken bir hata oluştu.");
      }
    } catch (err) {
      console.error("Failed to upload E-Nabız file:", err);
      setUploadError("Ağ bağlantı hatası oluştu.");
    } finally {
      setUploadingEnabiz(false);
      e.target.value = "";
    }
  };

  const addChronicDisease = () => {
    if (!newDisease.trim() || !profile) return;
    if (!profile.chronic_diseases.includes(newDisease.trim())) {
      setProfile({ ...profile, chronic_diseases: [...profile.chronic_diseases, newDisease.trim()] });
    }
    setNewDisease("");
  };
  const removeChronicDisease = (name: string) => {
    if (!profile) return;
    setProfile({ ...profile, chronic_diseases: profile.chronic_diseases.filter(d => d !== name) });
  };
  const addAllergy = () => {
    if (!newAllergy.trim() || !profile) return;
    if (!profile.allergies.includes(newAllergy.trim())) {
      setProfile({ ...profile, allergies: [...profile.allergies, newAllergy.trim()] });
    }
    setNewAllergy("");
  };
  const removeAllergy = (name: string) => {
    if (!profile) return;
    setProfile({ ...profile, allergies: profile.allergies.filter(a => a !== name) });
  };
  const addMedication = () => {
    if (!newMed.trim() || !profile) return;
    if (!profile.active_medications.includes(newMed.trim())) {
      setProfile({ ...profile, active_medications: [...profile.active_medications, newMed.trim()] });
    }
    setNewMed("");
  };
  const removeMedication = (name: string) => {
    if (!profile) return;
    setProfile({ ...profile, active_medications: profile.active_medications.filter(m => m !== name) });
  };

  const bmi = profile ? (profile.weight / Math.pow(profile.height / 100, 2)) : 0;
  
  const getBmiStatus = (val: number) => {
    if (val < 18.5) return { label: t("Zayıf"), color: "text-blue-400", shadow: "drop-shadow-[0_0_10px_rgba(96,165,250,0.8)]" };
    if (val < 25) return { label: t("Normal (Sağlıklı)"), color: "text-emerald-400", shadow: "drop-shadow-[0_0_10px_rgba(52,211,153,0.8)]" };
    if (val < 30) return { label: t("Fazla Kilolu"), color: "text-amber-400", shadow: "drop-shadow-[0_0_10px_rgba(251,191,36,0.8)]" };
    return { label: t("Obezite"), color: "text-red-500", shadow: "drop-shadow-[0_0_10px_rgba(239,68,68,0.8)]" };
  };

  const getBmiDegrees = (val: number) => {
    const minBmi = 15; const maxBmi = 35;
    const clamped = Math.max(minBmi, Math.min(maxBmi, val));
    const percent = (clamped - minBmi) / (maxBmi - minBmi);
    return -90 + percent * 180;
  };

  if (loading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-[#080B0F] text-slate-400 min-h-[500px]">
        <RefreshCw className="size-10 animate-spin mb-4 text-[var(--accent-status)]" />
        <span className="tracking-widest uppercase text-sm">{t("Sağlık Profili Yükleniyor...")}</span>
      </div>
    );
  }

  if (!profile) return null;

  const bmiValue =
    profile && profile.height > 0
      ? profile.weight / Math.pow(profile.height / 100, 2)
      : null;

  /* Künye hücreleri: hepsi GERÇEK veriden türetilir. Uydurma değer yok. */
  const heroCells = profile
    ? [
        profile.blood_type ? `${t("KAN")} ${profile.blood_type}` : null,
        bmiValue ? `BMI ${bmiValue.toFixed(1)}` : null,
        `${profile.chronic_diseases.length} ${t("KRONİK")}`,
        `${profile.allergies.length} ${t("ALERJİ")}`,
        `${profile.active_medications.length} ${t("İLAÇ")}`,
      ].filter(Boolean) as string[]
    : [];

  const adminRecord: AdminRecord = profile?.admin_record ?? {};
  const patchAdmin = (patch: Partial<AdminRecord>) =>
    setProfile((prev) =>
      prev ? { ...prev, admin_record: { ...(prev.admin_record ?? {}), ...patch } } : prev
    );

  return (
    <div
      data-profile-scroll
      className="prof-page relative min-h-[calc(100vh-100px)] flex-1 overflow-y-auto pb-20 font-sans"
    >
      
      <RevealBlocks />

      {/* Başlık sahnesi: zemin `gözü_gösterdikten_sonra_hemen.mp4`
          (repoda 05-act.mp4 — verilen iki dosya byte-byte aynı). */}
      <ProfileHero
        kicker={t("Hasta kaydı · ArgusLens")}
        title={<>{t("SAĞLIK")} <span className="t-counter">{t("profilin")}</span></>}
        copy={t(
          "Biyometrik ölçümler, klinik geçmiş ve optik kalibrasyon tek kayıtta. Veriler yalnız bu cihazda tutulur; dışarı çıkmadan önce filtreden geçer."
        )}
        cells={heroCells}
      />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 space-y-8">
        
        <PatientRecord record={adminRecord} onChange={patchAdmin} />

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* LEFT COLUMN: BIOMETRICS & BMI */}
          <div className="space-y-8">
            
            {/* BIOMETRIC INPUTS */}
            <motion.div 
              initial={{ opacity: 0, y: 30 }} 
              whileInView={{ opacity: 1, y: 0 }} 
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.6 }}
              className="vis-plate group relative overflow-hidden" data-reveal-block
            >

              <div className="flex items-center gap-3 border-b border-[var(--edge-hair)] pb-4 mb-6 relative z-10">
                <User className="size-4" />
                <h2 className="t-dial">{t("BİYOMETRİK ÖLÇÜMLER")}</h2>
              </div>

              <div className="space-y-5 text-sm relative z-10">
                {[
                  { label: t("Yaş"), value: profile.age, key: "age", type: "number" },
                  { label: "Boy (cm)", value: profile.height, key: "height", type: "number" },
                  { label: "Kilo (kg)", value: profile.weight, key: "weight", type: "number" },
                ].map((item) => (
                  <div key={item.key} className="flex justify-between items-center group/input">
                    <span className="text-xs text-slate-400 tracking-wide uppercase group-hover/input:text-slate-300 transition-colors">{item.label}</span>
                    <input
                      type={item.type}
                      value={item.value}
                      onChange={(e) => setProfile({ ...profile, [item.key]: parseFloat(e.target.value) || 0 })}
                      className="w-20 bg-[color-mix(in_oklch,var(--p-graphite-990)_62%,transparent)] border border-[var(--edge-hair)] focus:border-[var(--accent-status-edge)] rounded-lg text-right px-3 py-1.5 text-[var(--ink-title)] focus:outline-none transition-all font-bold"
                    />
                  </div>
                ))}

                <div className="flex justify-between items-center group/input">
                  <span className="text-xs text-slate-400 tracking-wide uppercase group-hover/input:text-slate-300 transition-colors">{t("Kan Grubu")}</span>
                  <select
                    value={profile.blood_type}
                    onChange={(e) => setProfile({ ...profile, blood_type: e.target.value })}
                    className="w-24 bg-[color-mix(in_oklch,var(--p-graphite-990)_62%,transparent)] border border-[var(--edge-hair)] focus:border-[var(--accent-status-edge)] rounded-lg px-2 py-1.5 text-[var(--ink-title)] focus:outline-none transition-all font-bold cursor-pointer"
                  >
                    {["A Rh+", "A Rh-", "B Rh+", "B Rh-", "AB Rh+", "AB Rh-", "0 Rh+", "0 Rh-"].map(t => (
                      <option key={t} value={t} className="bg-[#111827]">{t}</option>
                    ))}
                  </select>
                </div>

                <div className="flex justify-between items-center group/input">
                  <span className="text-xs text-slate-400 tracking-wide uppercase group-hover/input:text-slate-300 transition-colors">{t("Cinsiyet")}</span>
                  <select
                    value={profile.gender}
                    onChange={(e) => setProfile({ ...profile, gender: e.target.value })}
                    className="w-24 bg-[color-mix(in_oklch,var(--p-graphite-990)_62%,transparent)] border border-[var(--edge-hair)] focus:border-[var(--accent-status-edge)] rounded-lg px-2 py-1.5 text-[var(--ink-title)] focus:outline-none transition-all font-bold cursor-pointer"
                  >
                    <option value="Erkek" className="bg-[#111827]">{t("Erkek")}</option>
                    <option value="Kadın" className="bg-[#111827]">{t("Kadın")}</option>
                  </select>
                </div>

                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={handleSaveProfile}
                  disabled={saving}
                  className="w-full mt-6 h-12 rounded-xl text-black font-bold tracking-widest uppercase cursor-pointer disabled:opacity-50 transition-all duration-300 flex justify-center items-center gap-2 hover:"
                  style={{ background: "linear-gradient(135deg, #0EA5E9, #00D4FF)" }}
                >
                  {saving ? <RefreshCw className="size-5 animate-spin" /> : <Save className="size-5" />}
                  {t("PROFİLİ KAYDET")}
                </motion.button>
              </div>
            </motion.div>

            {/* BMI GAUGE */}
            <motion.div 
              initial={{ opacity: 0, y: 30 }} 
              whileInView={{ opacity: 1, y: 0 }} 
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.6, delay: 0.2 }}
              className="vis-plate group relative flex flex-col items-center overflow-hidden" data-reveal-block
            >

              <div className="w-full flex items-center justify-between border-b border-[var(--edge-hair)] pb-4 mb-6 relative z-10">
                <div className="flex items-center gap-3">
                  <Gauge className="size-4" />
                  <h2 className="t-dial">{t("BMI İNDEKSİ")}</h2>
                </div>
              </div>

              <div className="relative w-64 h-36 mt-4 overflow-hidden flex items-center justify-center z-10">
                <svg className="w-full h-full drop-shadow-2xl" viewBox="0 0 100 50">
                  <path d="M 10 50 A 40 40 0 0 1 90 50" fill="none" stroke="#222" strokeWidth="6" strokeLinecap="round" />
                  <path d="M 10 50 A 40 40 0 0 1 28 22" fill="none" stroke="#3B82F6" strokeWidth="6" />
                  <path d="M 28 22 A 40 40 0 0 1 60 11" fill="none" stroke="#10B981" strokeWidth="6" />
                  <path d="M 60 11 A 40 40 0 0 1 80 24" fill="none" stroke="#F59E0B" strokeWidth="6" />
                  <path d="M 80 24 A 40 40 0 0 1 90 50" fill="none" stroke="#EF4444" strokeWidth="6" />
                  <g transform="translate(50, 50)">
                    <line 
                      x1="0" y1="0" x2="0" y2="-40" 
                      stroke="#FFF" strokeWidth="3" strokeLinecap="round"
                      style={{ 
                        transform: `rotate(${getBmiDegrees(bmi)}deg)`,
                        transformOrigin: '0px 0px',
                        transition: 'transform 1.2s cubic-bezier(0.34, 1.56, 0.64, 1)' 
                      }} 
                    />
                    <circle cx="0" cy="0" r="5" fill="#00D4FF" className="drop-" />
                  </g>
                </svg>
              </div>

              <div className="text-center font-mono mt-4 relative z-10">
                <div className="text-4xl font-black text-slate-100 tracking-tighter">{bmi.toFixed(1)}</div>
                <div className={`text-sm font-bold mt-2 ${getBmiStatus(bmi).color} ${getBmiStatus(bmi).shadow} uppercase tracking-widest`}>
                  {getBmiStatus(bmi).label}
                </div>
              </div>
            </motion.div>

          </div>

          {/* MIDDLE COLUMN: E-NABIZ & AI REPORT */}
          <div className="space-y-8 lg:col-span-2">
            
            {/* E-NABIZ PORTAL */}
            <motion.div 
              initial={{ opacity: 0, y: 30 }} 
              whileInView={{ opacity: 1, y: 0 }} 
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.6, delay: 0.3 }}
              className="vis-plate relative overflow-hidden" data-reveal-block
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-[var(--edge-hair)] pb-4 mb-6 gap-4">
                <div className="flex items-center gap-3">
                  <Activity className="size-4" />
                  <h2 className="t-dial">{t("E-NABIZ SAĞLIK GEÇMİŞİ")}</h2>
                </div>
                <span className="cell whitespace-nowrap">{t("Entegre Sistem")}</span>
              </div>

              <div className="flex gap-4 border-b border-[rgba(255,255,255,0.06)] mb-6 overflow-x-auto pb-1 scrollbar-hide">
                {(["visits", "prescriptions", "labs"] as const).map(tab => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`pb-3 text-sm tracking-widest uppercase transition-all relative whitespace-nowrap px-2 ${
                      activeTab === tab
                        ? "text-[var(--accent-status-soft)] font-semibold"
                        : "text-slate-500 hover:text-slate-300"
                    }`}
                  >
                    {tab === "visits" && t("Muayeneler")}
                    {tab === "prescriptions" && t("Reçeteler")}
                    {tab === "labs" && t("Laboratuvar")}
                    {activeTab === tab && (
                      <motion.div layoutId="activeTab" className="absolute bottom-0 left-0 right-0 h-px bg-[var(--accent-status)]" />
                    )}
                  </button>
                ))}
              </div>

              <div className="min-h-[200px]">
                <AnimatePresence mode="wait">
                  <motion.div
                    key={activeTab}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    transition={{ duration: 0.3 }}
                    className="overflow-x-auto"
                  >
                    {activeTab === "visits" && (
                      <table className="w-full text-xs text-left border-collapse min-w-[500px]">
                        <thead>
                          <tr className="border-b border-[rgba(255,255,255,0.06)] text-slate-500 uppercase tracking-widest">
                            <th className="py-3 px-4 font-normal text-xs">{t("Tarih")}</th>
                            <th className="py-3 px-4 font-normal text-xs">{t("Bölüm")}</th>
                            <th className="py-3 px-4 font-normal text-xs">{t("Hekim")}</th>
                            <th className="py-3 px-4 font-normal text-xs">{t("Tanı")}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {profile.visit_history?.map((v, i) => (
                            <motion.tr
                              initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}
                              key={i} className="border-b border-[rgba(255,255,255,0.04)] hover:bg-slate-800/30 transition-colors"
                            >
                              <td className="py-4 px-4 whitespace-nowrap text-slate-400">{v.date}</td>
                              <td className="py-4 px-4 text-[var(--ink-title)]">{v.dept}</td>
                              <td className="py-4 px-4 text-white">{v.doctor}</td>
                              <td className="py-4 px-4 text-slate-300">{v.diagnosis}</td>
                            </motion.tr>
                          ))}
                        </tbody>
                      </table>
                    )}

                    {activeTab === "prescriptions" && (
                      <table className="w-full text-xs text-left border-collapse min-w-[500px]">
                        <thead>
                          <tr className="border-b border-[rgba(255,255,255,0.06)] text-slate-500 uppercase tracking-widest">
                            <th className="py-3 px-4 font-normal text-xs">{t("Tarih")}</th>
                            <th className="py-3 px-4 font-normal text-xs">{t("Hekim")}</th>
                            <th className="py-3 px-4 font-normal text-xs">{t("İlaçlar")}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {profile.prescriptions?.map((p, i) => (
                            <motion.tr
                              initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}
                              key={i} className="border-b border-[rgba(255,255,255,0.04)] hover:bg-slate-800/30 transition-colors"
                            >
                              <td className="py-4 px-4 whitespace-nowrap text-slate-400">{p.date}</td>
                              <td className="py-4 px-4 text-[var(--ink-title)]">{p.doctor}</td>
                              <td className="py-4 px-4 flex flex-wrap gap-2">
                                {p.meds?.map((m, mi) => (
                                  <span key={mi} className="bg-[color-mix(in_oklch,var(--p-graphite-990)_62%,transparent)] border border-[var(--edge-hair)] px-2 py-1 rounded text-[10px] tracking-wider text-slate-300">{m}</span>
                                ))}
                              </td>
                            </motion.tr>
                          ))}
                        </tbody>
                      </table>
                    )}

                    {activeTab === "labs" && (
                      <table className="w-full text-xs text-left border-collapse min-w-[500px]">
                        <thead>
                          <tr className="border-b border-[rgba(255,255,255,0.06)] text-slate-500 uppercase tracking-widest">
                            <th className="py-3 px-4 font-normal text-xs">{t("Tarih")}</th>
                            <th className="py-3 px-4 font-normal text-xs">{t("Test")}</th>
                            <th className="py-3 px-4 font-normal text-xs">{t("Değer")}</th>
                            <th className="py-3 px-4 font-normal text-xs">{t("Durum")}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {profile.lab_results?.map((l, i) => (
                            <motion.tr
                              initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}
                              key={i} className="border-b border-[rgba(255,255,255,0.04)] hover:bg-slate-800/30 transition-colors"
                            >
                              <td className="py-4 px-4 whitespace-nowrap text-slate-400">{l.date}</td>
                              <td className="py-4 px-4 text-[var(--ink-title)]">{l.test}</td>
                              <td className="py-4 px-4 font-bold text-white text-sm">{l.value}</td>
                              <td className="py-4 px-4">
                                <span className={`px-3 py-1 rounded text-[10px] tracking-widest uppercase font-bold border ${
                                  l.status === "Normal" 
                                    ? "bg-[var(--measure-wash)] border-[var(--edge-live)] text-[var(--measure)]"
                                    : l.status.includes("Yüksek")
                                      ? "bg-red-500/10 border-red-500/20 text-red-500"
                                      : "bg-amber-500/10 border-amber-500/20 text-amber-400"
                                }`}>
                                  {l.status}
                                </span>
                              </td>
                            </motion.tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </motion.div>
                </AnimatePresence>
              </div>

              {/* UPLOAD PANEL */}
              <div className="mt-8 pt-6 border-t border-[rgba(255,255,255,0.06)]">
                <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-2 mb-4">
                  <span className="text-xs font-bold text-slate-300 tracking-widest uppercase">{t("E-NABIZ RAPORU YÜKLE (YAPAY ZEKA)")}</span>
                  <span className="t-dial">{t("PDF, TXT, XML, HTML")}</span>
                </div>

                <div className="group/upload relative flex flex-col justify-between gap-6 rounded-[var(--p-radius-plate)] border border-dashed border-[var(--edge-rule)] bg-[color-mix(in_oklch,var(--p-graphite-990)_55%,transparent)] p-6 transition-colors duration-300 hover:border-[var(--accent-status-edge)] sm:flex-row sm:items-center">
                  <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
                    <div className="rounded-[var(--p-radius-cell)] border border-[var(--edge-hair)] bg-[color-mix(in_oklch,var(--p-graphite-990)_55%,transparent)] p-3 text-[var(--ink-title)] transition-colors group-hover/upload:border-[var(--edge-rule)]">
                      {uploadingEnabiz ? <RefreshCw className="size-6 animate-spin" /> : <Upload className="size-6" />}
                    </div>
                    <div className="text-left">
                      <p className="text-sm font-bold text-white tracking-wider">
                        {t(uploadingEnabiz ? "Yapay Zeka Çözümlüyor..." : "Dosyayı Seçin veya Sürükleyin")}
                      </p>
                      <p className="text-xs text-slate-500 mt-1">{t("E-Nabız sisteminden alınan sağlık raporu PDF veya metin dosyası.")}</p>
                    </div>
                  </div>

                  <label className="btn btn-ghost w-full shrink-0 cursor-pointer sm:w-auto">{t("DOSYA SEÇ")}<input type="file" accept=".pdf,.txt,.xml,.html,.json" onChange={handleFileUpload} disabled={uploadingEnabiz} className="hidden" />
                  </label>
                </div>

                {uploadSuccess && (
                  <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="mt-4 flex items-center gap-2 t-measure">
                    <Check className="size-4" />{t("E-Nabız verileri başarıyla sisteme aktarıldı!")}</motion.div>
                )}
                {uploadError && (
                  <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="mt-4 text-xs text-red-500 font-bold tracking-widest uppercase flex items-center gap-2">
                    <ShieldAlert className="size-4" /> {uploadError}
                  </motion.div>
                )}
              </div>
            </motion.div>

            {/* AI REPORT MODULE */}
            <motion.div 
              initial={{ opacity: 0, y: 30 }} 
              whileInView={{ opacity: 1, y: 0 }} 
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.6, delay: 0.4 }}
              className="vis-plate relative overflow-hidden" data-reveal-block
            >
              <div className="absolute top-0 right-0 size-40 bg-purple-500/5 blur-3xl rounded-full pointer-events-none" />

              <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-[rgba(255,255,255,0.06)] pb-4 mb-6 relative z-10 gap-4">
                <div className="flex items-center gap-3">
                  <Sparkles className="size-6 text-purple-400 animate-pulse" />
                  <h2 className="t-dial">{t("YAPAY ZEKA KLİNİK EPİKRİZ")}</h2>
                </div>
                <span className="text-[10px] font-mono bg-purple-500/10 text-purple-400 border border-purple-500/20 px-3 py-1 rounded-full uppercase tracking-widest whitespace-nowrap">{t("Powered by GPT-4o")}</span>
              </div>

              <p className="text-xs text-slate-400 font-mono mb-6 leading-relaxed relative z-10">{t("Tüm biometrik profiliniz, geçmiş E-Nabız verileriniz ve ArgusLens anlık telemetriniz RAG ile analiz edilerek profesyonel bir klinik rapor üretilir.")}</p>

              <div className="flex flex-col sm:flex-row gap-4 relative z-10">
                <motion.button
                  whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                  onClick={handleGenerateAIReport} disabled={generatingReport}
                  className="flex-1 flex items-center justify-center gap-2 py-4 rounded-xl border border-purple-500/40 bg-purple-500/10 hover:bg-purple-500/20 hover:border-purple-500/60 text-purple-300 text-sm font-bold font-mono tracking-widest uppercase cursor-pointer disabled:opacity-50 transition-all shadow-[0_0_15px_rgba(168,85,247,0.15)]"
                >
                  {generatingReport ? <><RefreshCw className="size-5 animate-spin" />{t("RAPOR ÜRETİLİYOR...")}</> : <><Sparkles className="size-5" />{t("RAPOR ÜRET")}</>}
                </motion.button>
                
                {aiReport && (
                  <motion.button
                    initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }}
                    whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                    onClick={handleDownloadReport}
                    className="px-6 py-4 rounded-xl border border-[var(--edge-rule)] bg-[var(--accent-status-wash)] hover:bg-[var(--accent-status-wash)] text-[var(--accent-status-soft)] font-bold cursor-pointer transition-all flex items-center justify-center shadow-[0_0_15px_rgba(6,182,212,0.15)]"
                  >
                    <Download className="size-5" />
                  </motion.button>
                )}
              </div>

              <AnimatePresence>
                {aiReport && (
                  <motion.div 
                    initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
                    className="mt-6 p-6 border border-[rgba(255,255,255,0.06)] bg-[#050505] rounded-2xl max-h-[400px] overflow-y-auto text-sm text-slate-300 leading-loose font-mono whitespace-pre-wrap selection:bg-purple-500/30"
                  >
                    {aiReport}
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>

          </div>

        </div>

        {/* BOTTOM ROW: MEDICAL TAGS & HARDWARE CALIBRATION */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          
          {/* MEDICAL TAGS */}
          <motion.div 
            initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-50px" }} transition={{ duration: 0.6, delay: 0.5 }}
            className="card-lift bg-gradient-to-br from-[#0D1117] to-[#111827] border border-[var(--edge-hair)] hover:border-red-500/40 rounded-2xl p-6 transition-colors duration-300"
          >
             <h2 className="text-xl font-black tracking-widest text-slate-200 uppercase mb-6 flex items-center gap-3 border-b border-[rgba(255,255,255,0.06)] pb-4">
                <Heart className="size-6 text-red-500" />{t("TIBBİ DURUM ETİKETLERİ")}</h2>

             {/* Chronic */}
             <div className="mb-6">
               <div className="text-xs font-bold font-mono tracking-widest text-slate-500 uppercase mb-3">{t("Kronik Hastalıklar")}</div>
               <div className="flex flex-wrap gap-2 mb-3">
                 {profile.chronic_diseases.map(disease => (
                   <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} key={disease} className="bg-[#111] border border-[#333] hover:border-red-500/50 text-slate-300 text-xs font-mono px-3 py-1.5 rounded-lg flex items-center gap-2 transition-colors">
                     {disease}
                     <button onClick={() => removeChronicDisease(disease)} className="text-red-500 hover:text-red-400 font-bold focus:outline-none cursor-pointer">×</button>
                   </motion.span>
                 ))}
               </div>
               <div className="flex gap-2">
                 <input type="text" placeholder={t("Hastalık ekle...")} value={newDisease} onChange={(e) => setNewDisease(e.target.value)} className="flex-1 bg-[#111] border border-[#333] focus:border-red-500/50 rounded-lg px-4 py-2 text-xs font-mono text-white focus:outline-none" />
                 <button onClick={addChronicDisease} className="bg-[#111] border border-[#333] hover:border-red-500/50 hover:bg-red-500/10 px-4 rounded-lg text-red-500 transition-colors cursor-pointer"><Plus className="size-4" /></button>
               </div>
             </div>

             {/* Allergies */}
             <div className="mb-6">
               <div className="text-xs font-bold font-mono tracking-widest text-slate-500 uppercase mb-3">{t("Alerjiler")}</div>
               <div className="flex flex-wrap gap-2 mb-3">
                 {profile.allergies.map(allergy => (
                   <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} key={allergy} className="bg-[#111] border border-[#333] hover:border-amber-500/50 text-slate-300 text-xs font-mono px-3 py-1.5 rounded-lg flex items-center gap-2 transition-colors">
                     {allergy}
                     <button onClick={() => removeAllergy(allergy)} className="text-amber-500 hover:text-amber-400 font-bold focus:outline-none cursor-pointer">×</button>
                   </motion.span>
                 ))}
               </div>
               <div className="flex gap-2">
                 <input type="text" placeholder={t("Alerji ekle...")} value={newAllergy} onChange={(e) => setNewAllergy(e.target.value)} className="flex-1 bg-[#111] border border-[#333] focus:border-amber-500/50 rounded-lg px-4 py-2 text-xs font-mono text-white focus:outline-none" />
                 <button onClick={addAllergy} className="bg-[#111] border border-[#333] hover:border-amber-500/50 hover:bg-amber-500/10 px-4 rounded-lg text-amber-500 transition-colors cursor-pointer"><Plus className="size-4" /></button>
               </div>
             </div>

             {/* Medications */}
             <div>
               <div className="text-xs font-bold font-mono tracking-widest text-slate-500 uppercase mb-3">{t("Aktif İlaçlar")}</div>
               <div className="flex flex-wrap gap-2 mb-3">
                 {profile.active_medications.map(med => (
                   <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} key={med} className="bg-[#111] border border-[#333] hover:border-[var(--edge-rule)] text-slate-300 text-xs font-mono px-3 py-1.5 rounded-lg flex items-center gap-2 transition-colors">
                     {med}
                     <button onClick={() => removeMedication(med)} className="text-[var(--accent-status-soft)] hover:text-[var(--accent-status-soft)] font-bold focus:outline-none cursor-pointer">×</button>
                   </motion.span>
                 ))}
               </div>
               <div className="flex gap-2">
                 <input type="text" placeholder={t("İlaç ekle...")} value={newMed} onChange={(e) => setNewMed(e.target.value)} className="flex-1 bg-[#111] border border-[#333] focus:border-[var(--accent-status-edge)]/50 rounded-lg px-4 py-2 text-xs font-mono text-white focus:outline-none" />
                 <button onClick={addMedication} className="bg-[#111] border border-[#333] hover:border-[var(--edge-rule)] hover:bg-[var(--accent-status-wash)] px-4 rounded-lg text-[var(--accent-status-soft)] transition-colors cursor-pointer"><Plus className="size-4" /></button>
               </div>
             </div>

          </motion.div>

          {/* HARDWARE CALIBRATION & WATER */}
          <motion.div 
            initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-50px" }} transition={{ duration: 0.6, delay: 0.6 }}
            className="card-lift bg-gradient-to-br from-[#0D1117] to-[#111827] border border-[var(--edge-hair)] hover:border-[rgba(0,212,255,0.4)] rounded-2xl p-6 transition-colors duration-300 flex flex-col justify-between"
          >
             <div>
               <div className="flex items-center justify-between border-b border-[rgba(255,255,255,0.06)] pb-4 mb-6">
                  <div className="flex items-center gap-3">
                    <Zap className="size-6 text-[var(--accent-status-soft)] animate-pulse drop-" />
                    <h2 className="t-dial">{t("DONANIM KALİBRASYONU")}</h2>
                  </div>
                  <span className="text-[10px] font-mono bg-[var(--accent-status-wash)] text-[var(--accent-status-soft)] border border-[var(--edge-rule)] px-3 py-1 rounded-full uppercase tracking-widest flex items-center gap-2">
                    <span className="size-2 animate-ping rounded-full bg-[var(--accent-status)]" />{t("BAĞLI")}</span>
               </div>

               <div className="space-y-8 font-mono">
                 {/* IOP */}
                 <div className="space-y-3">
                   <div className="flex justify-between text-sm uppercase tracking-widest">
                     <span className="text-slate-500">{t("IOP Baz Basıncı")}</span>
                     <span className="text-[var(--accent-status-soft)] font-bold">{profile.iop_calibration.toFixed(1)} mmHg</span>
                   </div>
                   <input 
                     type="range" min="5" max="30" step="0.5" value={profile.iop_calibration}
                     onChange={(e) => setProfile({ ...profile, iop_calibration: parseFloat(e.target.value) })}
                     className="w-full h-2 bg-[color-mix(in_oklch,var(--p-bone-500)_14%,transparent)] rounded-lg appearance-none cursor-pointer accent-[var(--accent-status)] transition-all"
                   />
                 </div>

                 {/* Glucose */}
                 <div className="space-y-3">
                   <div className="flex justify-between text-sm uppercase tracking-widest">
                     <span className="text-slate-500">{t("Glikoz Katsayısı")}</span>
                     <span className="text-[var(--accent-status-soft)] font-bold">{profile.glucose_calibration.toFixed(2)}x</span>
                   </div>
                   <input 
                     type="range" min="0.1" max="5.0" step="0.05" value={profile.glucose_calibration}
                     onChange={(e) => setProfile({ ...profile, glucose_calibration: parseFloat(e.target.value) })}
                     className="w-full h-2 bg-[color-mix(in_oklch,var(--p-bone-500)_14%,transparent)] rounded-lg appearance-none cursor-pointer accent-[var(--accent-status)] transition-all"
                   />
                 </div>
               </div>
             </div>

             <div className="space-y-6 pt-6 border-t border-[rgba(255,255,255,0.06)] mt-8 font-mono">
               {/* WATER */}
               <div className="space-y-3">
                 <div className="flex justify-between text-xs uppercase tracking-widest items-center">
                   <span className="text-slate-500 flex items-center gap-2"><Droplet className="size-4 text-[var(--accent-status-soft)]" />{t("Su Tüketimi")}</span>
                   <span className="text-[var(--accent-status-soft)] font-bold">{profile.daily_water_intake} / 2500 ml</span>
                 </div>
                 <div className="w-full bg-[#111] border border-[rgba(255,255,255,0.06)] rounded-full h-3 overflow-hidden shadow-inner">
                   <motion.div 
                     initial={{ width: 0 }} animate={{ width: `${Math.min(100, (profile.daily_water_intake / 2500) * 100)}%` }} transition={{ duration: 1 }}
                     className="h-full rounded-full bg-[var(--measure)]" 
                   />
                 </div>
                 <div className="flex gap-4 mt-4">
                   <button onClick={() => handleAddWater(250)} className="flex-1 py-3 text-xs tracking-widest uppercase border border-[#333] hover:border-[var(--edge-rule)] bg-[#111] hover:bg-[var(--accent-status-wash)] text-[var(--accent-status-soft)] rounded-xl cursor-pointer transition-all font-bold">{t("+250 ML")}</button>
                   <button onClick={() => handleAddWater(500)} className="flex-1 py-3 text-xs tracking-widest uppercase border border-[#333] hover:border-[var(--edge-rule)] bg-[#111] hover:bg-[var(--accent-status-wash)] text-[var(--accent-status-soft)] rounded-xl cursor-pointer transition-all font-bold">{t("+500 ML")}</button>
                 </div>
               </div>
             </div>
          </motion.div>
        </div>

      </div>

      {/* EMERGENCY MODAL (CINEMATIC) */}
      <AnimatePresence>
      </AnimatePresence>

    </div>
  );
}
