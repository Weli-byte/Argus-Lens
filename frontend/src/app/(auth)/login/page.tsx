"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Eye, EyeOff, AlertCircle, Lock, User } from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { setAccessToken } from "@/lib/api-client";
import { useAuthStore } from "@/store/auth-store";
import ParticleField from "@/components/ui/ParticleField";

export default function LoginPage() {
  const router = useRouter();
  const { isAuthenticated, setAuth } = useAuthStore();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isAuthenticated) router.replace("/dashboard");
  }, [isAuthenticated, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError("Kullanıcı adı ve şifre gerekli");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const tokens = await apiClient.login(username.trim(), password);
      setAccessToken(tokens.access_token);
      setAuth(
        { username: username.trim(), role: "operator" },
        tokens.access_token,
        tokens.refresh_token
      );
      router.replace("/dashboard");
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Kimlik doğrulama başarısız. Bilgilerinizi kontrol edin.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col lg:flex-row">
      {/* ── LEFT — Hero ─────────────────────────────────────────────── */}
      <div
        className="relative lg:w-[55%] flex flex-col items-center justify-center overflow-hidden py-16 lg:py-0 min-h-[40vh]"
        style={{
          background:
            "radial-gradient(ellipse 70% 60% at 40% 45%, #0a1628 0%, #080B0F 75%)",
        }}
      >
        <ParticleField density={50} className="absolute inset-0 w-full h-full" />
        <div className="absolute size-[500px] rounded-full border border-cyan-500/10" />
        <div className="absolute size-[380px] rounded-full border border-dashed border-cyan-500/15 animate-[spin_30s_linear_infinite]" />
        <div className="absolute size-[380px] rounded-full border border-cyan-500/15 animate-[ring-pulse_3.5s_ease-out_infinite]" />

        {/* Blinking bionic eye */}
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.9, ease: "easeOut" }}
          className="relative"
        >
          <svg
            viewBox="0 0 120 80"
            className="w-52 animate-[blink_4s_ease-in-out_infinite] drop-shadow-[0_0_40px_rgba(0,212,255,0.35)]"
            style={{ transformOrigin: "60px 40px" }}
          >
            <path
              d="M8 40 Q60 4 112 40 Q60 76 8 40 Z"
              fill="none"
              stroke="#00D4FF"
              strokeOpacity="0.5"
              strokeWidth="2"
            />
            <circle cx="60" cy="40" r="16" fill="rgba(0,212,255,0.08)" stroke="#00D4FF" strokeWidth="2" />
            <circle cx="60" cy="40" r="7" fill="#00D4FF" />
            <circle cx="63" cy="37" r="2" fill="#F8FAFC" opacity="0.85" />
          </svg>
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.25, ease: "easeOut" }}
          className="relative mt-8 font-black tracking-tighter uppercase text-center"
          style={{ fontSize: "clamp(2.6rem, 5.5vw, 4.5rem)", lineHeight: 0.95 }}
        >
          <span className="text-white">ARGUS</span>
          <span className="text-cyan-400 drop-shadow-[0_0_28px_rgba(0,212,255,0.45)]">LENS</span>
        </motion.h1>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.7, delay: 0.5 }}
          className="relative w-56 h-px bg-gradient-to-r from-transparent via-cyan-400 to-transparent my-5"
        />

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.7, delay: 0.6 }}
          className="relative text-slate-400 tracking-[0.3em] text-xs uppercase text-center px-6"
        >
          Biyonik Lens AI Platform
        </motion.p>

        {/* Mini stats */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.8 }}
          className="relative flex gap-10 mt-10"
        >
          {[
            { n: "22", l: "Simülasyon" },
            { n: "GPT-4o", l: "Vision AI" },
            { n: "<2s", l: "Analiz" },
          ].map((s) => (
            <div key={s.l} className="text-center">
              <p className="text-xl font-extrabold text-cyan-400">{s.n}</p>
              <p className="text-[10px] text-slate-500 uppercase tracking-widest mt-0.5">{s.l}</p>
            </div>
          ))}
        </motion.div>
      </div>

      {/* ── RIGHT — Form ────────────────────────────────────────────── */}
      <div className="flex-1 flex items-center justify-center p-6 lg:p-12 relative">
        <div
          aria-hidden
          className="ambient-grid pointer-events-none absolute inset-0"
        />
        <motion.div
          initial={{ opacity: 0, x: 24 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.6, delay: 0.2, ease: "easeOut" }}
          className="relative w-full max-w-sm"
        >
          <div className="rounded-2xl border border-[rgba(0,212,255,0.15)] bg-gradient-to-br from-[#0D1117] to-[#111827] p-8 shadow-[0_24px_60px_rgba(0,0,0,0.5)] space-y-7">
            <div>
              <h2 className="text-2xl font-black text-white tracking-tight">Giriş Yap</h2>
              <p className="text-xs text-slate-500 mt-1">
                Operatör konsoluna erişmek için kimlik doğrulayın
              </p>
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-[10px] uppercase tracking-widest text-slate-400 font-semibold">
                  Kullanıcı Adı
                </label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-slate-500 pointer-events-none" />
                  <input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    autoComplete="username"
                    spellCheck={false}
                    className="w-full rounded-lg border border-[rgba(255,255,255,0.08)] bg-slate-800/50 pl-10 pr-3 py-2.5 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-cyan-500 focus:shadow-[0_0_16px_rgba(0,212,255,0.1)] transition-all"
                    placeholder="admin"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] uppercase tracking-widest text-slate-400 font-semibold">
                  Şifre
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-slate-500 pointer-events-none" />
                  <input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="current-password"
                    className="w-full rounded-lg border border-[rgba(255,255,255,0.08)] bg-slate-800/50 pl-10 pr-10 py-2.5 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-cyan-500 focus:shadow-[0_0_16px_rgba(0,212,255,0.1)] transition-all"
                    placeholder="••••••••"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-cyan-400 transition-colors"
                    tabIndex={-1}
                  >
                    {showPassword ? (
                      <EyeOff className="size-4" />
                    ) : (
                      <Eye className="size-4" />
                    )}
                  </button>
                </div>
              </div>

              {error && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  className="flex items-center gap-2 text-xs text-red-400 bg-red-500/5 border border-red-500/20 rounded-lg px-3 py-2"
                >
                  <AlertCircle className="size-3.5 shrink-0" />
                  {error}
                </motion.div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full h-12 rounded-xl bg-gradient-to-r from-cyan-500 to-sky-500 text-[#080B0F] text-sm font-bold tracking-wide transition-all duration-300 hover:shadow-[0_0_28px_rgba(0,212,255,0.45)] hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
              >
                {loading ? "Doğrulanıyor…" : "Giriş Yap"}
              </button>
            </form>

            <p className="text-center text-[10px] text-slate-600 uppercase tracking-widest">
              Yalnızca yetkili personel
            </p>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
