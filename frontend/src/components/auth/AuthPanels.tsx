"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle, ArrowLeft, Eye, EyeOff, Loader2 } from "lucide-react";
import { apiClient, setAccessToken } from "@/lib/api-client";
import { useAuthStore } from "@/store/auth-store";
import { useT } from "@/lib/i18n";
import type { AuthTokens, User } from "@/types";
import SocialAuth from "./SocialAuth";

/** Giriş sonrası hedef. Eski `/dashboard` tanıtım ekranı kaldırıldı. */
const AFTER_AUTH = "/dashboard/vision";

/** Tek panel, tek akış. Ayrı 01/02 bölümleri kaldırıldı. */
type Mode = "login" | "register";
type Step = "main" | "phone" | "otp";

function errorText(err: unknown, fallback: string): string {
  if (typeof err === "object" && err !== null) {
    const e = err as {
      response?: { data?: { detail?: unknown } };
      message?: string;
      code?: string;
    };
    const detail = e.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (e.code === "ERR_NETWORK" || e.message === "Network Error") {
      return "Sunucuya ulaşılamadı. Backend çalışıyor mu?";
    }
    if (e.message) return e.message;
  }
  return fallback;
}

export default function AuthPanels() {
  const t = useT();
  const router = useRouter();
  const { isAuthenticated, setAuth } = useAuthStore();

  const [mode, setMode] = useState<Mode>("login");
  const [step, setStep] = useState<Step>("main");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  // Giriş
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);

  // Telefon / kod
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");

  // Kayıt
  const [fullName, setFullName] = useState("");
  const [regMethod, setRegMethod] = useState<"email" | "phone">("email");
  const [regValue, setRegValue] = useState("");
  const [consent, setConsent] = useState(false);

  useEffect(() => {
    if (isAuthenticated) router.replace(AFTER_AUTH);
  }, [isAuthenticated, router]);

  /** Sunucu rolünü `User["role"]` birleşimine daraltır; tanınmayan rol en dar
      yetkiye düşer. */
  const narrowRole = (value: string | undefined): User["role"] =>
    value === "admin" || value === "operator" || value === "viewer"
      ? value
      : "viewer";

  const complete = useCallback(
    (tokens: AuthTokens, fallbackName: string) => {
      setAccessToken(tokens.access_token);
      setAuth(
        {
          username: tokens.user?.username ?? fallbackName,
          role: narrowRole(tokens.user?.role),
        },
        tokens.access_token,
        tokens.refresh_token
      );
      router.replace(AFTER_AUTH);
    },
    [router, setAuth]
  );

  const run = useCallback(async (fn: () => Promise<void>, fallback: string) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(t(errorText(err, fallback)));
    } finally {
      setBusy(false);
    }
  }, [t]);

  const handleOAuth = useCallback(
    (provider: "google" | "apple", idToken: string) => {
      void run(async () => {
        const tokens = await apiClient.oauthLogin(provider, idToken);
        complete(tokens, provider);
      }, t("Sosyal giriş başarısız."));
    },
    [complete, run, t]
  );

  const switchMode = (next: Mode) => {
    setMode(next);
    setStep("main");
    setError(null);
    setInfo(null);
  };

  const submitLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (!identifier.trim() || !password) {
      setError(t("Kullanıcı adı/e-posta ve parola gerekli."));
      return;
    }
    void run(async () => {
      const tokens = await apiClient.login(identifier.trim(), password);
      complete(tokens, identifier.trim());
    }, t("Giriş başarısız."));
  };

  const submitRegister = (e: React.FormEvent) => {
    e.preventDefault();
    if (!consent) {
      setError(t("Devam etmek için aydınlatma metnini onaylayın."));
      return;
    }
    void run(async () => {
      const tokens = await apiClient.register({
        full_name: fullName.trim(),
        email: regMethod === "email" ? regValue.trim() : "",
        phone: regMethod === "phone" ? regValue.trim() : "",
        password,
      });
      complete(tokens, regValue.trim());
    }, t("Kayıt tamamlanamadı."));
  };

  const requestCode = (e: React.FormEvent) => {
    e.preventDefault();
    setInfo(null);
    void run(async () => {
      const res = await apiClient.requestOtp(phone);
      setPhone(res.phone);
      setStep("otp");
      setInfo(
        res.dev_code
          ? `SMS sağlayıcısı yapılandırılmadı. Geliştirme kodu: ${res.dev_code}`
          : t("Kod telefonunuza gönderildi.")
      );
    }, t("Kod gönderilemedi."));
  };

  const verifyCode = (e: React.FormEvent) => {
    e.preventDefault();
    void run(async () => {
      const tokens = await apiClient.verifyOtp(phone, code);
      complete(tokens, phone);
    }, t("Kod doğrulanamadı."));
  };

  const onPhoneStep = step === "phone" || step === "otp";

  return (
    <section className="auth-section">
      <div className="auth-panel">
        <header className="mb-[var(--p-space-4)]">
          <p className="t-dial mb-[var(--p-space-3)]">
            {t("ArgusLens · Operatör konsolu")}
          </p>
          <h1 className="t-display-sm" style={{ fontSize: "var(--p-text-xl)" }}>
            {t(
              onPhoneStep
                ? "Telefonla giriş"
                : mode === "login"
                  ? "Konsola gir"
                  : "Hesap aç"
            )}
          </h1>
          <p className="t-body mt-[var(--p-space-2)] text-[var(--p-text-sm)]">
            {t(
              onPhoneStep
                ? "Numaranıza gönderilen kodu girin."
                : "Google, Apple, e-posta veya telefon ile."
            )}
          </p>
        </header>

        {!onPhoneStep && (
          <>
            <div className="auth-tabs" role="tablist" aria-label={t("Kimlik yöntemi")}>
              {(["login", "register"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  role="tab"
                  aria-selected={mode === m}
                  className="auth-tab"
                  onClick={() => switchMode(m)}
                >
                  {t(m === "login" ? "Giriş yap" : "Kayıt ol")}
                </button>
              ))}
            </div>

            <div className="grid gap-[var(--p-space-3)]">
              <SocialAuth
                onToken={handleOAuth}
                onError={setError}
                disabled={busy}
              />
              <p className="auth-divider">
                <span>{t("veya")}</span>
              </p>
            </div>
          </>
        )}

        {/* ── GİRİŞ ── */}
        {mode === "login" && step === "main" && (
          <form
            key="login"
            onSubmit={submitLogin}
            className="auth-step mt-[var(--p-space-3)] grid gap-[var(--p-space-3)]"
          >
            <Field
              id="li-id"
              label={t("E-posta, telefon veya kullanıcı adı")}
              value={identifier}
              onChange={setIdentifier}
              autoComplete="username"
              placeholder="ornek@arguslens.dev"
            />
            <PasswordField
              id="li-pw"
              label={t("Parola")}
              value={password}
              onChange={setPassword}
              show={showPw}
              toggle={() => setShowPw((v) => !v)}
              autoComplete="current-password"
            />
            <Notes error={error} info={info} />
            <button
              type="submit"
              className="btn btn-primary w-full"
              disabled={busy}
            >
              {busy && <Loader2 className="size-4 animate-spin" />}
              Giriş yap
            </button>
            <button
              type="button"
              className="btn btn-ghost w-full"
              onClick={() => {
                setStep("phone");
                setError(null);
              }}
            >
              {t("Telefona kod gönder")}
            </button>
          </form>
        )}

        {/* ── KAYIT ── */}
        {mode === "register" && step === "main" && (
          <form
            key="register"
            onSubmit={submitRegister}
            className="auth-step mt-[var(--p-space-3)] grid gap-[var(--p-space-3)]"
          >
            <Field
              id="rg-name"
              label="Ad soyad"
              value={fullName}
              onChange={setFullName}
              autoComplete="name"
            />

            <fieldset>
              <legend className="auth-label">{t("Kayıt yöntemi")}</legend>
              <div className="grid grid-cols-2 gap-[var(--p-space-2)]">
                {(["email", "phone"] as const).map((m) => (
                  <button
                    key={m}
                    type="button"
                    aria-pressed={regMethod === m}
                    onClick={() => {
                      setRegMethod(m);
                      setRegValue("");
                      setError(null);
                    }}
                    className="auth-provider justify-center"
                    style={
                      regMethod === m
                        ? {
                            borderColor: "var(--measure)",
                            color: "var(--measure)",
                          }
                        : undefined
                    }
                  >
                    {t(m === "email" ? "E-posta" : "Telefon")}
                  </button>
                ))}
              </div>
            </fieldset>

            <Field
              id="rg-id"
              label={t(
                regMethod === "email" ? "E-posta adresi" : "Telefon numarası"
              )}
              value={regValue}
              onChange={setRegValue}
              type={regMethod === "email" ? "email" : "tel"}
              autoComplete={regMethod === "email" ? "email" : "tel"}
              placeholder={
                regMethod === "email"
                  ? "ornek@arguslens.dev"
                  : "+90 555 111 22 33"
              }
            />

            <PasswordField
              id="rg-pw"
              label={t("Parola")}
              value={password}
              onChange={setPassword}
              show={showPw}
              toggle={() => setShowPw((v) => !v)}
              autoComplete="new-password"
              hint={t("En az 8 karakter, harf ve rakam içermeli.")}
            />

            <label className="flex items-start gap-[var(--p-space-2)] text-[var(--p-text-xs)] text-[var(--ink-body)]">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                className="mt-[3px] size-4 accent-[var(--measure)]"
              />
              <span>
                {t(
                  "Sağlık verilerimin klinik karar desteği amacıyla işlenmesine ilişkin aydınlatma metnini okudum ve onaylıyorum."
                )}
              </span>
            </label>

            <Notes error={error} info={info} />
            <button
              type="submit"
              className="btn btn-primary w-full"
              disabled={busy}
            >
              {busy && <Loader2 className="size-4 animate-spin" />}
              {t("Hesabı oluştur")}
            </button>
          </form>
        )}

        {/* ── TELEFON ── */}
        {step === "phone" && (
          <form
            key="phone"
            onSubmit={requestCode}
            className="auth-step grid gap-[var(--p-space-3)]"
          >
            <Field
              id="li-phone"
              label={t("Telefon numarası")}
              value={phone}
              onChange={setPhone}
              type="tel"
              autoComplete="tel"
              placeholder="+90 555 111 22 33"
            />
            <Notes error={error} info={info} />
            <button
              type="submit"
              className="btn btn-primary w-full"
              disabled={busy}
            >
              {busy && <Loader2 className="size-4 animate-spin" />}
              {t("Kod gönder")}
            </button>
            <BackButton
              onClick={() => {
                setStep("main");
                setError(null);
                setInfo(null);
              }}
            />
          </form>
        )}

        {/* ── KOD ── */}
        {step === "otp" && (
          <form
            key="otp"
            onSubmit={verifyCode}
            className="auth-step grid gap-[var(--p-space-3)]"
          >
            <div>
              <label className="auth-label" htmlFor="li-otp">
                {phone} numarasına gönderilen kod
              </label>
              <input
                id="li-otp"
                className="auth-input auth-otp"
                value={code}
                onChange={(e) =>
                  setCode(e.target.value.replace(/\D/g, "").slice(0, 6))
                }
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                placeholder="000000"
              />
            </div>
            <Notes error={error} info={info} />
            <button
              type="submit"
              className="btn btn-primary w-full"
              disabled={busy || code.length < 6}
            >
              {busy && <Loader2 className="size-4 animate-spin" />}
              Doğrula ve gir
            </button>
            <BackButton
              onClick={() => {
                setStep("phone");
                setError(null);
              }}
            />
          </form>
        )}
      </div>
    </section>
  );
}

/* ── Ortak parçalar ───────────────────────────────────────────────────── */
function Field({
  id,
  label,
  value,
  onChange,
  type = "text",
  autoComplete,
  placeholder,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  autoComplete?: string;
  placeholder?: string;
}) {
  return (
    <div>
      <label className="auth-label" htmlFor={id}>
        {label}
      </label>
      <input
        id={id}
        className="auth-input"
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete}
        placeholder={placeholder}
        spellCheck={false}
        inputMode={
          type === "tel" ? "tel" : type === "email" ? "email" : undefined
        }
      />
    </div>
  );
}

function PasswordField({
  id,
  label,
  value,
  onChange,
  show,
  toggle,
  autoComplete,
  hint,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  show: boolean;
  toggle: () => void;
  autoComplete: string;
  hint?: string;
}) {
  const t = useT();
  return (
    <div>
      <label className="auth-label" htmlFor={id}>
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          className="auth-input pr-[var(--p-space-7)]"
          type={show ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          autoComplete={autoComplete}
        />
        <button
          type="button"
          onClick={toggle}
          className="absolute right-[var(--p-space-3)] top-1/2 -translate-y-1/2 text-[var(--ink-mute)] hover:text-[var(--ink-title)]"
          aria-label={t(show ? "Parolayı gizle" : "Parolayı göster")}
        >
          {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
        </button>
      </div>
      {hint && (
        <p className="mt-[var(--p-space-2)] text-[var(--p-text-3xs)] text-[var(--ink-faint)]">
          {hint}
        </p>
      )}
    </div>
  );
}

function Notes({ error, info }: { error: string | null; info: string | null }) {
  return (
    <>
      {error && (
        <p className="auth-note auth-note-error" role="alert">
          <AlertCircle className="mt-[2px] size-4 shrink-0" />
          <span>{error}</span>
        </p>
      )}
      {info && !error && (
        <p className="auth-note auth-note-info" role="status">
          <span>{info}</span>
        </p>
      )}
    </>
  );
}

function BackButton({ onClick }: { onClick: () => void }) {
  const t = useT();
  return (
    <button type="button" className="btn btn-ghost w-full" onClick={onClick}>
      <ArrowLeft className="size-3.5" />
      {t("Geri")}
    </button>
  );
}
