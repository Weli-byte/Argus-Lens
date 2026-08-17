"use client";

import React, { useState, useEffect } from "react";
import { 
  User, ShieldAlert, Info, Heart, Droplet, Plus, Trash2, Gauge, 
  Activity, Sparkles, FileText, Check, Save, RefreshCw, ChevronRight, 
  Phone, Zap, Download, Upload 
} from "lucide-react";
import { useVitalStream } from "@/hooks/useVitalStream";
import { motion, AnimatePresence } from "framer-motion";

interface VisitRecord { date: string; dept: string; doctor: string; diagnosis: string; }
interface PrescriptionRecord { date: string; doctor: string; meds: string[]; }
interface LabRecord { date: string; test: string; value: string; status: string; }

interface ProfileState {
  age: number; height: number; weight: number; blood_type: string; gender: string;
  chronic_diseases: string[]; allergies: string[]; active_medications: string[];
  iop_calibration: number; glucose_calibration: number; daily_water_intake: number;
  visit_history: VisitRecord[]; prescriptions: PrescriptionRecord[]; lab_results: LabRecord[];
}

export default function HealthProfilePage() {
  const { currentTelemetry } = useVitalStream();

  const [profile, setProfile] = useState<ProfileState | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState<"visits" | "prescriptions" | "labs">("visits");

  const [newDisease, setNewDisease] = useState("");
  const [newAllergy, setNewAllergy] = useState("");
  const [newMed, setNewMed] = useState("");

  const [aiReport, setAiReport] = useState<string | null>(null);
  const [generatingReport, setGeneratingReport] = useState(false);

  const [showEmergencyModal, setShowEmergencyModal] = useState(false);
  const [emergencyPhone, setEmergencyPhone] = useState("+90 532 123 45 67");

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
          daily_water_intake: profile.daily_water_intake
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
    if (val < 18.5) return { label: "Zayıf", color: "text-blue-400", shadow: "drop-shadow-[0_0_10px_rgba(96,165,250,0.8)]" };
    if (val < 25) return { label: "Normal (Sağlıklı)", color: "text-emerald-400", shadow: "drop-shadow-[0_0_10px_rgba(52,211,153,0.8)]" };
    if (val < 30) return { label: "Fazla Kilolu", color: "text-amber-400", shadow: "drop-shadow-[0_0_10px_rgba(251,191,36,0.8)]" };
    return { label: "Obezite", color: "text-red-500", shadow: "drop-shadow-[0_0_10px_rgba(239,68,68,0.8)]" };
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
        <RefreshCw className="size-10 animate-spin mb-4 text-cyan-400 drop-shadow-[0_0_15px_rgba(0,212,255,0.6)]" />
        <span className="tracking-widest uppercase text-sm">Sağlık Profili Yükleniyor...</span>
      </div>
    );
  }

  if (!profile) return null;

  return (
    <div className="flex-1 text-slate-100 min-h-[calc(100vh-100px)] overflow-y-auto font-sans relative selection:bg-cyan-500/30 pb-20">
      
      {/* FLOATING EMERGENCY BUTTON */}
      <motion.button 
        whileHover={{ scale: 1.1 }} 
        whileTap={{ scale: 0.95 }}
        onClick={() => setShowEmergencyModal(true)}
        className="fixed bottom-8 right-8 z-50 bg-red-600 hover:bg-red-500 text-white rounded-full p-4 shadow-[0_0_30px_rgba(220,38,38,0.6)] animate-pulse flex items-center justify-center cursor-pointer border border-red-400"
      >
        <ShieldAlert className="size-8" />
      </motion.button>

      {/* HERO SECTION - PARALLAX FEEL */}
      <motion.div 
        initial={{ opacity: 0, y: -20 }} 
        animate={{ opacity: 1, y: 0 }} 
        transition={{ duration: 0.8, ease: "easeOut" }}
        className="relative py-20 px-8 border-b border-[rgba(0,212,255,0.08)] overflow-hidden flex flex-col items-center justify-center"
      >
        <div className="absolute inset-0 bg-gradient-to-b from-cyan-900/10 to-transparent z-0 pointer-events-none" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-cyan-500/5 blur-[120px] rounded-full z-0 pointer-events-none" />

        <h1
          className="relative z-10 font-black tracking-tighter uppercase mb-5 text-center"
          style={{ fontSize: "clamp(3rem, 8vw, 6rem)", fontWeight: 900 }}
        >
          {"SAĞLIK".split("").map((ch, i) => (
            <span
              key={`s-${i}`}
              className="inline-block text-white"
              style={{ opacity: 0, animation: `charIn 0.5s ease forwards ${i * 0.05}s` }}
            >
              {ch}
            </span>
          ))}
          <span className="inline-block">&nbsp;</span>
          {"PROFİLİN".split("").map((ch, i) => (
            <span
              key={`p-${i}`}
              className="inline-block text-cyan-400 drop-shadow-[0_0_24px_rgba(0,212,255,0.35)]"
              style={{ opacity: 0, animation: `charIn 0.5s ease forwards ${(i + 7) * 0.05}s` }}
            >
              {ch}
            </span>
          ))}
        </h1>
        <div className="relative z-10 w-72 max-w-full h-px bg-gradient-to-r from-transparent via-cyan-400 to-transparent mb-5" />
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1, delay: 0.5 }}
          className="relative z-10 text-slate-400 tracking-[0.3em] text-sm uppercase text-center"
        >
          Argus Lens Biyometrik Profil & Optik Kalibrasyon Sistemi
        </motion.p>
      </motion.div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 space-y-8">
        
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* LEFT COLUMN: BIOMETRICS & BMI */}
          <div className="space-y-8">
            
            {/* BIOMETRIC INPUTS */}
            <motion.div 
              initial={{ opacity: 0, y: 30 }} 
              whileInView={{ opacity: 1, y: 0 }} 
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.6 }}
              className="card-lift bg-gradient-to-br from-[#0D1117] to-[#111827] border border-[rgba(0,212,255,0.15)] hover:border-[rgba(0,212,255,0.4)] rounded-2xl p-6 transition-colors duration-300 group relative overflow-hidden"
            >
              <div className="absolute -top-10 -right-10 size-32 bg-cyan-500/5 blur-3xl rounded-full group-hover:bg-cyan-500/10 transition-colors" />

              <div className="flex items-center gap-3 border-b border-[rgba(0,212,255,0.12)] pb-4 mb-6 relative z-10">
                <User className="size-6 text-cyan-400" />
                <h2 className="text-lg font-black tracking-widest text-slate-100 uppercase">BİYOMETRİK ÖLÇÜMLER</h2>
              </div>

              <div className="space-y-5 text-sm relative z-10">
                {[
                  { label: "Yaş", value: profile.age, key: "age", type: "number" },
                  { label: "Boy (cm)", value: profile.height, key: "height", type: "number" },
                  { label: "Kilo (kg)", value: profile.weight, key: "weight", type: "number" },
                ].map((item) => (
                  <div key={item.key} className="flex justify-between items-center group/input">
                    <span className="text-xs text-slate-400 tracking-wide uppercase group-hover/input:text-slate-300 transition-colors">{item.label}</span>
                    <input
                      type={item.type}
                      value={item.value}
                      onChange={(e) => setProfile({ ...profile, [item.key]: parseFloat(e.target.value) || 0 })}
                      className="w-20 bg-slate-800/50 border border-[rgba(255,255,255,0.08)] focus:border-cyan-500 rounded-lg text-right px-3 py-1.5 text-slate-100 focus:outline-none transition-all font-bold"
                    />
                  </div>
                ))}

                <div className="flex justify-between items-center group/input">
                  <span className="text-xs text-slate-400 tracking-wide uppercase group-hover/input:text-slate-300 transition-colors">Kan Grubu</span>
                  <select
                    value={profile.blood_type}
                    onChange={(e) => setProfile({ ...profile, blood_type: e.target.value })}
                    className="w-24 bg-slate-800/50 border border-[rgba(255,255,255,0.08)] focus:border-cyan-500 rounded-lg px-2 py-1.5 text-slate-100 focus:outline-none transition-all font-bold cursor-pointer"
                  >
                    {["A Rh+", "A Rh-", "B Rh+", "B Rh-", "AB Rh+", "AB Rh-", "0 Rh+", "0 Rh-"].map(t => (
                      <option key={t} value={t} className="bg-[#111827]">{t}</option>
                    ))}
                  </select>
                </div>

                <div className="flex justify-between items-center group/input">
                  <span className="text-xs text-slate-400 tracking-wide uppercase group-hover/input:text-slate-300 transition-colors">Cinsiyet</span>
                  <select
                    value={profile.gender}
                    onChange={(e) => setProfile({ ...profile, gender: e.target.value })}
                    className="w-24 bg-slate-800/50 border border-[rgba(255,255,255,0.08)] focus:border-cyan-500 rounded-lg px-2 py-1.5 text-slate-100 focus:outline-none transition-all font-bold cursor-pointer"
                  >
                    <option value="Erkek" className="bg-[#111827]">Erkek</option>
                    <option value="Kadın" className="bg-[#111827]">Kadın</option>
                  </select>
                </div>

                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={handleSaveProfile}
                  disabled={saving}
                  className="w-full mt-6 h-12 rounded-xl text-black font-bold tracking-widest uppercase cursor-pointer disabled:opacity-50 transition-all duration-300 flex justify-center items-center gap-2 hover:shadow-[0_0_24px_rgba(0,212,255,0.4)]"
                  style={{ background: "linear-gradient(135deg, #0EA5E9, #00D4FF)" }}
                >
                  {saving ? <RefreshCw className="size-5 animate-spin" /> : <Save className="size-5" />}
                  PROFİLİ KAYDET
                </motion.button>
              </div>
            </motion.div>

            {/* BMI GAUGE */}
            <motion.div 
              initial={{ opacity: 0, y: 30 }} 
              whileInView={{ opacity: 1, y: 0 }} 
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.6, delay: 0.2 }}
              className="card-lift bg-gradient-to-br from-[#0D1117] to-[#111827] border border-[rgba(0,212,255,0.15)] hover:border-[rgba(0,212,255,0.4)] rounded-2xl p-6 transition-colors duration-300 group relative overflow-hidden flex flex-col items-center"
            >
              <div className="absolute -bottom-10 -left-10 size-32 bg-cyan-500/5 blur-3xl rounded-full group-hover:bg-cyan-500/10 transition-colors" />

              <div className="w-full flex items-center justify-between border-b border-[rgba(0,212,255,0.12)] pb-4 mb-6 relative z-10">
                <div className="flex items-center gap-3">
                  <Gauge className="size-6 text-cyan-400" />
                  <h2 className="text-lg font-black tracking-widest text-slate-100 uppercase">BMI İNDEKSİ</h2>
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
                    <circle cx="0" cy="0" r="5" fill="#00D4FF" className="drop-shadow-[0_0_8px_rgba(0,212,255,0.8)]" />
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
              className="card-lift bg-gradient-to-br from-[#0D1117] to-[#111827] border border-[rgba(0,212,255,0.15)] hover:border-[rgba(0,212,255,0.4)] rounded-2xl p-6 transition-colors duration-300 relative overflow-hidden"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-[rgba(0,212,255,0.12)] pb-4 mb-6 gap-4">
                <div className="flex items-center gap-3">
                  <Activity className="size-6 text-cyan-400" />
                  <h2 className="text-lg font-black tracking-widest text-slate-100 uppercase">E-NABIZ SAĞLIK GEÇMİŞİ</h2>
                </div>
                <span className="text-[10px] tracking-widest text-cyan-400 border border-cyan-500/30 px-3 py-1 rounded-full uppercase whitespace-nowrap">
                  Entegre Sistem
                </span>
              </div>

              <div className="flex gap-4 border-b border-[rgba(255,255,255,0.06)] mb-6 overflow-x-auto pb-1 scrollbar-hide">
                {(["visits", "prescriptions", "labs"] as const).map(tab => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`pb-3 text-sm tracking-widest uppercase transition-all relative whitespace-nowrap px-2 ${
                      activeTab === tab
                        ? "text-cyan-400 font-semibold"
                        : "text-slate-500 hover:text-slate-300"
                    }`}
                  >
                    {tab === "visits" && "Muayeneler"}
                    {tab === "prescriptions" && "Reçeteler"}
                    {tab === "labs" && "Laboratuvar"}
                    {activeTab === tab && (
                      <motion.div layoutId="activeTab" className="absolute bottom-0 left-0 right-0 h-0.5 bg-cyan-400 shadow-[0_0_10px_rgba(0,212,255,0.6)]" />
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
                            <th className="py-3 px-4 font-normal text-xs">Tarih</th>
                            <th className="py-3 px-4 font-normal text-xs">Bölüm</th>
                            <th className="py-3 px-4 font-normal text-xs">Hekim</th>
                            <th className="py-3 px-4 font-normal text-xs">Tanı</th>
                          </tr>
                        </thead>
                        <tbody>
                          {profile.visit_history?.map((v, i) => (
                            <motion.tr
                              initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}
                              key={i} className="border-b border-[rgba(255,255,255,0.04)] hover:bg-slate-800/30 transition-colors"
                            >
                              <td className="py-4 px-4 whitespace-nowrap text-slate-400">{v.date}</td>
                              <td className="py-4 px-4 text-cyan-400 font-medium">{v.dept}</td>
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
                            <th className="py-3 px-4 font-normal text-xs">Tarih</th>
                            <th className="py-3 px-4 font-normal text-xs">Hekim</th>
                            <th className="py-3 px-4 font-normal text-xs">İlaçlar</th>
                          </tr>
                        </thead>
                        <tbody>
                          {profile.prescriptions?.map((p, i) => (
                            <motion.tr
                              initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}
                              key={i} className="border-b border-[rgba(255,255,255,0.04)] hover:bg-slate-800/30 transition-colors"
                            >
                              <td className="py-4 px-4 whitespace-nowrap text-slate-400">{p.date}</td>
                              <td className="py-4 px-4 text-cyan-400 font-medium">{p.doctor}</td>
                              <td className="py-4 px-4 flex flex-wrap gap-2">
                                {p.meds?.map((m, mi) => (
                                  <span key={mi} className="bg-slate-800/50 border border-[rgba(255,255,255,0.08)] px-2 py-1 rounded text-[10px] tracking-wider text-slate-300">{m}</span>
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
                            <th className="py-3 px-4 font-normal text-xs">Tarih</th>
                            <th className="py-3 px-4 font-normal text-xs">Test</th>
                            <th className="py-3 px-4 font-normal text-xs">Değer</th>
                            <th className="py-3 px-4 font-normal text-xs">Durum</th>
                          </tr>
                        </thead>
                        <tbody>
                          {profile.lab_results?.map((l, i) => (
                            <motion.tr
                              initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}
                              key={i} className="border-b border-[rgba(255,255,255,0.04)] hover:bg-slate-800/30 transition-colors"
                            >
                              <td className="py-4 px-4 whitespace-nowrap text-slate-400">{l.date}</td>
                              <td className="py-4 px-4 text-cyan-400 font-medium">{l.test}</td>
                              <td className="py-4 px-4 font-bold text-white text-sm">{l.value}</td>
                              <td className="py-4 px-4">
                                <span className={`px-3 py-1 rounded text-[10px] tracking-widest uppercase font-bold border ${
                                  l.status === "Normal" 
                                    ? "bg-cyan-500/10 border-cyan-500/20 text-cyan-400"
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
                  <span className="text-xs font-bold text-slate-300 tracking-widest uppercase">E-NABIZ RAPORU YÜKLE (YAPAY ZEKA)</span>
                  <span className="text-[10px] text-cyan-400">PDF, TXT, XML, HTML</span>
                </div>

                <div className="relative border-2 border-dashed border-[rgba(0,212,255,0.2)] hover:border-cyan-500/50 bg-[#080B0F]/60 hover:bg-cyan-500/5 rounded-2xl p-6 transition-all duration-300 flex flex-col sm:flex-row sm:items-center justify-between gap-6 group/upload">
                  <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
                    <div className="bg-cyan-500/5 p-3 rounded-xl border border-[rgba(0,212,255,0.2)] group-hover/upload:border-cyan-500/40 text-cyan-400 transition-colors">
                      {uploadingEnabiz ? <RefreshCw className="size-6 animate-spin" /> : <Upload className="size-6" />}
                    </div>
                    <div className="text-left">
                      <p className="text-sm font-bold text-white tracking-wider">
                        {uploadingEnabiz ? "Yapay Zeka Çözümlüyor..." : "Dosyayı Seçin veya Sürükleyin"}
                      </p>
                      <p className="text-xs text-slate-500 mt-1">
                        E-Nabız sisteminden alınan sağlık raporu PDF veya metin dosyası.
                      </p>
                    </div>
                  </div>

                  <label className="shrink-0 text-xs px-6 py-3 rounded-xl border border-[rgba(0,212,255,0.3)] hover:bg-cyan-500/10 hover:shadow-[0_0_16px_rgba(0,212,255,0.15)] text-cyan-400 font-bold uppercase tracking-widest cursor-pointer transition-all duration-300 w-full sm:w-auto text-center">
                    DOSYA SEÇ
                    <input type="file" accept=".pdf,.txt,.xml,.html,.json" onChange={handleFileUpload} disabled={uploadingEnabiz} className="hidden" />
                  </label>
                </div>

                {uploadSuccess && (
                  <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="mt-4 text-xs text-cyan-400 font-bold tracking-widest uppercase flex items-center gap-2">
                    <Check className="size-4" /> E-Nabız verileri başarıyla sisteme aktarıldı!
                  </motion.div>
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
              className="card-lift bg-gradient-to-br from-[#0D1117] to-[#111827] border border-[rgba(0,212,255,0.15)] hover:border-purple-500/40 rounded-2xl p-6 transition-colors duration-300 relative overflow-hidden"
            >
              <div className="absolute top-0 right-0 size-40 bg-purple-500/5 blur-3xl rounded-full pointer-events-none" />

              <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-[rgba(255,255,255,0.06)] pb-4 mb-6 relative z-10 gap-4">
                <div className="flex items-center gap-3">
                  <Sparkles className="size-6 text-purple-400 animate-pulse" />
                  <h2 className="text-xl font-black tracking-widest text-slate-200 uppercase">YAPAY ZEKA KLİNİK EPİKRİZ</h2>
                </div>
                <span className="text-[10px] font-mono bg-purple-500/10 text-purple-400 border border-purple-500/20 px-3 py-1 rounded-full uppercase tracking-widest whitespace-nowrap">
                  Powered by GPT-4o
                </span>
              </div>

              <p className="text-xs text-slate-400 font-mono mb-6 leading-relaxed relative z-10">
                Tüm biometrik profiliniz, geçmiş E-Nabız verileriniz ve ArgusLens anlık telemetriniz RAG ile analiz edilerek profesyonel bir klinik rapor üretilir.
              </p>

              <div className="flex flex-col sm:flex-row gap-4 relative z-10">
                <motion.button
                  whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                  onClick={handleGenerateAIReport} disabled={generatingReport}
                  className="flex-1 flex items-center justify-center gap-2 py-4 rounded-xl border border-purple-500/40 bg-purple-500/10 hover:bg-purple-500/20 hover:border-purple-500/60 text-purple-300 text-sm font-bold font-mono tracking-widest uppercase cursor-pointer disabled:opacity-50 transition-all shadow-[0_0_15px_rgba(168,85,247,0.15)]"
                >
                  {generatingReport ? <><RefreshCw className="size-5 animate-spin" /> RAPOR ÜRETİLİYOR...</> : <><Sparkles className="size-5" /> RAPOR ÜRET</>}
                </motion.button>
                
                {aiReport && (
                  <motion.button
                    initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }}
                    whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                    onClick={handleDownloadReport}
                    className="px-6 py-4 rounded-xl border border-cyan-500/40 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-300 font-bold cursor-pointer transition-all flex items-center justify-center shadow-[0_0_15px_rgba(6,182,212,0.15)]"
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
            className="card-lift bg-gradient-to-br from-[#0D1117] to-[#111827] border border-[rgba(0,212,255,0.15)] hover:border-red-500/40 rounded-2xl p-6 transition-colors duration-300"
          >
             <h2 className="text-xl font-black tracking-widest text-slate-200 uppercase mb-6 flex items-center gap-3 border-b border-[rgba(255,255,255,0.06)] pb-4">
                <Heart className="size-6 text-red-500" /> TIBBİ DURUM ETİKETLERİ
             </h2>

             {/* Chronic */}
             <div className="mb-6">
               <div className="text-xs font-bold font-mono tracking-widest text-slate-500 uppercase mb-3">Kronik Hastalıklar</div>
               <div className="flex flex-wrap gap-2 mb-3">
                 {profile.chronic_diseases.map(disease => (
                   <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} key={disease} className="bg-[#111] border border-[#333] hover:border-red-500/50 text-slate-300 text-xs font-mono px-3 py-1.5 rounded-lg flex items-center gap-2 transition-colors">
                     {disease}
                     <button onClick={() => removeChronicDisease(disease)} className="text-red-500 hover:text-red-400 font-bold focus:outline-none cursor-pointer">×</button>
                   </motion.span>
                 ))}
               </div>
               <div className="flex gap-2">
                 <input type="text" placeholder="Hastalık ekle..." value={newDisease} onChange={(e) => setNewDisease(e.target.value)} className="flex-1 bg-[#111] border border-[#333] focus:border-red-500/50 rounded-lg px-4 py-2 text-xs font-mono text-white focus:outline-none" />
                 <button onClick={addChronicDisease} className="bg-[#111] border border-[#333] hover:border-red-500/50 hover:bg-red-500/10 px-4 rounded-lg text-red-500 transition-colors cursor-pointer"><Plus className="size-4" /></button>
               </div>
             </div>

             {/* Allergies */}
             <div className="mb-6">
               <div className="text-xs font-bold font-mono tracking-widest text-slate-500 uppercase mb-3">Alerjiler</div>
               <div className="flex flex-wrap gap-2 mb-3">
                 {profile.allergies.map(allergy => (
                   <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} key={allergy} className="bg-[#111] border border-[#333] hover:border-amber-500/50 text-slate-300 text-xs font-mono px-3 py-1.5 rounded-lg flex items-center gap-2 transition-colors">
                     {allergy}
                     <button onClick={() => removeAllergy(allergy)} className="text-amber-500 hover:text-amber-400 font-bold focus:outline-none cursor-pointer">×</button>
                   </motion.span>
                 ))}
               </div>
               <div className="flex gap-2">
                 <input type="text" placeholder="Alerji ekle..." value={newAllergy} onChange={(e) => setNewAllergy(e.target.value)} className="flex-1 bg-[#111] border border-[#333] focus:border-amber-500/50 rounded-lg px-4 py-2 text-xs font-mono text-white focus:outline-none" />
                 <button onClick={addAllergy} className="bg-[#111] border border-[#333] hover:border-amber-500/50 hover:bg-amber-500/10 px-4 rounded-lg text-amber-500 transition-colors cursor-pointer"><Plus className="size-4" /></button>
               </div>
             </div>

             {/* Medications */}
             <div>
               <div className="text-xs font-bold font-mono tracking-widest text-slate-500 uppercase mb-3">Aktif İlaçlar</div>
               <div className="flex flex-wrap gap-2 mb-3">
                 {profile.active_medications.map(med => (
                   <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} key={med} className="bg-[#111] border border-[#333] hover:border-cyan-500/50 text-slate-300 text-xs font-mono px-3 py-1.5 rounded-lg flex items-center gap-2 transition-colors">
                     {med}
                     <button onClick={() => removeMedication(med)} className="text-cyan-500 hover:text-cyan-400 font-bold focus:outline-none cursor-pointer">×</button>
                   </motion.span>
                 ))}
               </div>
               <div className="flex gap-2">
                 <input type="text" placeholder="İlaç ekle..." value={newMed} onChange={(e) => setNewMed(e.target.value)} className="flex-1 bg-[#111] border border-[#333] focus:border-cyan-500/50 rounded-lg px-4 py-2 text-xs font-mono text-white focus:outline-none" />
                 <button onClick={addMedication} className="bg-[#111] border border-[#333] hover:border-cyan-500/50 hover:bg-cyan-500/10 px-4 rounded-lg text-cyan-500 transition-colors cursor-pointer"><Plus className="size-4" /></button>
               </div>
             </div>

          </motion.div>

          {/* HARDWARE CALIBRATION & WATER */}
          <motion.div 
            initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-50px" }} transition={{ duration: 0.6, delay: 0.6 }}
            className="card-lift bg-gradient-to-br from-[#0D1117] to-[#111827] border border-[rgba(0,212,255,0.15)] hover:border-[rgba(0,212,255,0.4)] rounded-2xl p-6 transition-colors duration-300 flex flex-col justify-between"
          >
             <div>
               <div className="flex items-center justify-between border-b border-[rgba(255,255,255,0.06)] pb-4 mb-6">
                  <div className="flex items-center gap-3">
                    <Zap className="size-6 text-cyan-400 animate-pulse drop-shadow-[0_0_10px_rgba(0,212,255,0.7)]" />
                    <h2 className="text-xl font-black tracking-widest text-slate-200 uppercase">DONANIM KALİBRASYONU</h2>
                  </div>
                  <span className="text-[10px] font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 px-3 py-1 rounded-full uppercase tracking-widest flex items-center gap-2">
                    <span className="size-2 rounded-full bg-cyan-400 animate-ping" /> BAĞLI
                  </span>
               </div>

               <div className="space-y-8 font-mono">
                 {/* IOP */}
                 <div className="space-y-3">
                   <div className="flex justify-between text-sm uppercase tracking-widest">
                     <span className="text-slate-500">IOP Baz Basıncı</span>
                     <span className="text-cyan-400 font-bold">{profile.iop_calibration.toFixed(1)} mmHg</span>
                   </div>
                   <input 
                     type="range" min="5" max="30" step="0.5" value={profile.iop_calibration}
                     onChange={(e) => setProfile({ ...profile, iop_calibration: parseFloat(e.target.value) })}
                     className="w-full h-2 bg-[#1A2432] rounded-lg appearance-none cursor-pointer accent-cyan-500 hover:accent-cyan-400 transition-all"
                   />
                 </div>

                 {/* Glucose */}
                 <div className="space-y-3">
                   <div className="flex justify-between text-sm uppercase tracking-widest">
                     <span className="text-slate-500">Glikoz Katsayısı</span>
                     <span className="text-cyan-400 font-bold">{profile.glucose_calibration.toFixed(2)}x</span>
                   </div>
                   <input 
                     type="range" min="0.1" max="5.0" step="0.05" value={profile.glucose_calibration}
                     onChange={(e) => setProfile({ ...profile, glucose_calibration: parseFloat(e.target.value) })}
                     className="w-full h-2 bg-[#222] rounded-lg appearance-none cursor-pointer accent-cyan-500 hover:accent-cyan-400 transition-all"
                   />
                 </div>
               </div>
             </div>

             <div className="space-y-6 pt-6 border-t border-[rgba(255,255,255,0.06)] mt-8 font-mono">
               {/* WATER */}
               <div className="space-y-3">
                 <div className="flex justify-between text-xs uppercase tracking-widest items-center">
                   <span className="text-slate-500 flex items-center gap-2"><Droplet className="size-4 text-cyan-500" /> Su Tüketimi</span>
                   <span className="text-cyan-400 font-bold">{profile.daily_water_intake} / 2500 ml</span>
                 </div>
                 <div className="w-full bg-[#111] border border-[rgba(255,255,255,0.06)] rounded-full h-3 overflow-hidden shadow-inner">
                   <motion.div 
                     initial={{ width: 0 }} animate={{ width: `${Math.min(100, (profile.daily_water_intake / 2500) * 100)}%` }} transition={{ duration: 1 }}
                     className="bg-gradient-to-r from-cyan-600 to-cyan-400 h-full rounded-full drop-shadow-[0_0_8px_rgba(6,182,212,0.8)]" 
                   />
                 </div>
                 <div className="flex gap-4 mt-4">
                   <button onClick={() => handleAddWater(250)} className="flex-1 py-3 text-xs tracking-widest uppercase border border-[#333] hover:border-cyan-500/50 bg-[#111] hover:bg-cyan-500/10 text-cyan-400 rounded-xl cursor-pointer transition-all font-bold">+250 ML</button>
                   <button onClick={() => handleAddWater(500)} className="flex-1 py-3 text-xs tracking-widest uppercase border border-[#333] hover:border-cyan-500/50 bg-[#111] hover:bg-cyan-500/10 text-cyan-400 rounded-xl cursor-pointer transition-all font-bold">+500 ML</button>
                 </div>
               </div>
             </div>
          </motion.div>
        </div>

      </div>

      {/* EMERGENCY MODAL (CINEMATIC) */}
      <AnimatePresence>
        {showEmergencyModal && (
          <motion.div 
            initial={{ opacity: 0, backdropFilter: "blur(0px)" }} animate={{ opacity: 1, backdropFilter: "blur(20px)" }} exit={{ opacity: 0, backdropFilter: "blur(0px)" }}
            className="fixed inset-0 bg-black/90 flex items-center justify-center z-[100] p-4"
          >
            <motion.div 
              initial={{ scale: 0.9, y: 50, opacity: 0 }} animate={{ scale: 1, y: 0, opacity: 1 }} exit={{ scale: 0.9, y: 50, opacity: 0 }} transition={{ type: "spring", damping: 25, stiffness: 300 }}
              className="w-full max-w-md border border-red-600/50 bg-[#050505] rounded-3xl overflow-hidden shadow-[0_0_80px_rgba(220,38,38,0.3)] flex flex-col"
            >
              <div className="bg-gradient-to-r from-red-950/80 to-black border-b border-red-600/30 px-6 py-5 flex items-center gap-4">
                <ShieldAlert className="size-8 text-red-500 animate-pulse drop-shadow-[0_0_15px_rgba(239,68,68,0.8)]" />
                <div>
                  <h3 className="text-lg font-black font-mono tracking-widest text-red-500 uppercase">ACİL DURUM KARTI</h3>
                  <span className="text-xs text-red-400/60 font-mono tracking-widest uppercase">Emergency Protocol Active</span>
                </div>
              </div>

              <div className="p-8 flex flex-col items-center gap-8 text-center">
                <div className="p-4 bg-white rounded-2xl shadow-[0_0_40px_rgba(255,255,255,0.1)]">
                  <svg className="size-48 text-black" viewBox="0 0 100 100">
                    <path fill="currentColor" d="M0,0 h30 v30 h-30 z M10,10 h10 v10 h-10 z M70,0 h30 v30 h-30 z M80,10 h10 v10 h-10 z M0,70 h30 v30 h-30 z M10,80 h10 v10 h-10 z M40,10 h10 v10 h-10 z M50,30 h10 v10 h-10 z M30,50 h10 v10 h-10 z M50,50 h10 v10 h-10 z M80,40 h10 v10 h-10 z M70,70 h10 v10 h-10 z M90,80 h10 v10 h-10 z M40,80 h10 v10 h-10 z M50,90 h10 v10 h-10 z M60,60 h10 v10 h-10 z" />
                    <rect x="40" y="40" width="20" height="20" fill="currentColor" />
                    <rect x="0" y="0" width="5" height="5" fill="currentColor" />
                    <rect x="95" y="0" width="5" height="5" fill="currentColor" />
                    <rect x="0" y="95" width="5" height="5" fill="currentColor" />
                    <rect x="95" y="95" width="5" height="5" fill="currentColor" />
                  </svg>
                </div>
                
                <div className="w-full space-y-4 text-sm font-mono text-left bg-[#111] border border-[rgba(255,255,255,0.06)] p-6 rounded-2xl">
                  <div className="flex justify-between border-b border-[#333] pb-2">
                    <span className="text-slate-500 uppercase tracking-widest text-xs">Kan Grubu</span>
                    <span className="text-red-500 font-bold text-lg">{profile.blood_type}</span>
                  </div>
                  <div className="flex justify-between border-b border-[#333] pb-2">
                    <span className="text-slate-500 uppercase tracking-widest text-xs">Kronik</span>
                    <span className="text-white font-bold text-right truncate pl-4">{profile.chronic_diseases.join(', ') || 'Yok'}</span>
                  </div>
                  <div className="flex justify-between border-b border-[#333] pb-2">
                    <span className="text-slate-500 uppercase tracking-widest text-xs">Alerji</span>
                    <span className="text-white font-bold text-right truncate pl-4">{profile.allergies.join(', ') || 'Yok'}</span>
                  </div>
                  <div className="flex justify-between pt-1 items-center">
                    <span className="text-slate-500 uppercase tracking-widest text-xs">Acil Tel</span>
                    <div className="flex items-center gap-2">
                      <Phone className="size-4 text-green-500" />
                      <input type="text" value={emergencyPhone} onChange={(e) => setEmergencyPhone(e.target.value)} className="bg-transparent border-none text-right w-36 text-white font-bold focus:outline-none" />
                    </div>
                  </div>
                </div>

                <button onClick={() => setShowEmergencyModal(false)} className="w-full py-4 bg-red-600 hover:bg-red-500 text-white font-mono text-sm font-black tracking-widest uppercase rounded-xl cursor-pointer transition-all shadow-[0_0_20px_rgba(220,38,38,0.4)]">
                  MODALI KAPAT
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

    </div>
  );
}
