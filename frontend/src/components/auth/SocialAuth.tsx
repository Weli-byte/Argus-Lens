"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient } from "@/lib/api-client";

/* ────────────────────────────────────────────────────────────────────────────
   Google / Apple ile giriş.

   Akış: sağlayıcının JS kitaplığı bir KİMLİK TOKEN'I (JWT) verir; token
   sunucuya gönderilir, sunucu sağlayıcının JWKS anahtarıyla İMZASINI
   DOĞRULAR (bkz. core/oidc.py) ve ancak ondan sonra oturum açar.
   İstemci tarafında hiçbir güven varsayımı yok.

   Yapılandırma (frontend/.env.local):
     NEXT_PUBLIC_GOOGLE_CLIENT_ID=...apps.googleusercontent.com
     NEXT_PUBLIC_APPLE_CLIENT_ID=com.sirket.servis
   Backend tarafında da GOOGLE_CLIENT_ID / APPLE_CLIENT_ID gerekir.

   İstemci kimliği tanımlı değilse düğme ÇALIŞMIYOR gibi davranmaz —
   açıkça devre dışı görünür ve sebebini söyler. Sessizce ölen düğme yok.
   ────────────────────────────────────────────────────────────────────────── */

const GOOGLE_SRC = "https://accounts.google.com/gsi/client";
const APPLE_SRC =
  "https://appleid.cdn-apple.com/appleauth/static/jsapi/appleid/1/en_US/appleid.auth.js";

type GoogleCredentialResponse = { credential?: string };

/* prompt() sessizce başarısız olabiliyor (tarayıcıda Google oturumu yok,
   üçüncü taraf çerezleri kapalı, FedCM engelli…). Bildirim geri çağrısı
   olmadan kullanıcı hiçbir şey görmüyor. */
type GooglePromptNotification = {
  isNotDisplayed?: () => boolean;
  isSkippedMoment?: () => boolean;
  getNotDisplayedReason?: () => string;
  getSkippedReason?: () => string;
};

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (o: {
            client_id: string;
            callback: (r: GoogleCredentialResponse) => void;
            ux_mode?: string;

          }) => void;
          prompt: (cb?: (n: GooglePromptNotification) => void) => void;
        };
      };
    };
    AppleID?: {
      auth: {
        init: (o: {
          clientId: string;
          scope: string;
          redirectURI: string;
          usePopup: boolean;
        }) => void;
        signIn: () => Promise<{
          authorization?: { id_token?: string };
        }>;
      };
    };
  }
}

function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) return resolve();
    const s = document.createElement("script");
    s.src = src;
    s.async = true;
    s.defer = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error(`Yüklenemedi: ${src}`));
    document.head.appendChild(s);
  });
}

/* Derleme zamanı yedeği. Asıl kaynak backend'in /auth/providers ucudur:
   böylece kimliği yalnızca backend ortamına yazmak yeterli olur, frontend'i
   yeniden derlemek gerekmez. */
const ENV_GOOGLE_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? "";
const ENV_APPLE_ID = process.env.NEXT_PUBLIC_APPLE_CLIENT_ID ?? "";

type Props = {
  onToken: (provider: "google" | "apple", idToken: string) => void;
  onError: (message: string) => void;
  disabled?: boolean;
};
import { useT } from "@/lib/i18n";

export default function SocialAuth({ onToken, onError, disabled }: Props) {
  const t = useT();
  const [busy, setBusy] = useState<"google" | "apple" | null>(null);
  const [googleId, setGoogleId] = useState(ENV_GOOGLE_ID);
  const [appleId, setAppleId] = useState(ENV_APPLE_ID);
  const googleReady = useRef(false);

  // Backend'den çalışma zamanı yapılandırması
  useEffect(() => {
    let cancelled = false;
    apiClient
      .getAuthProviders()
      .then((p) => {
        if (cancelled) return;
        if (p.google?.client_id) setGoogleId(p.google.client_id);
        if (p.apple?.client_id) setAppleId(p.apple.client_id);
      })
      .catch(() => {
        /* backend kapalıysa derleme zamanı yedeği kullanılır */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!googleId) return;
    let cancelled = false;
    loadScript(GOOGLE_SRC)
      .then(() => {
        if (cancelled || !window.google) return;
        window.google.accounts.id.initialize({
          client_id: googleId,
          callback: (res) => {
            setBusy(null);
            if (res.credential) onToken("google", res.credential);
            else onError(t("Google kimlik token'ı alınamadı."));
          },
        });
        googleReady.current = true;
      })
      .catch(() => onError(t("Google oturum açma kitaplığı yüklenemedi.")));
    return () => {
      cancelled = true;
    };
  }, [googleId, onToken, onError, t]);

  useEffect(() => {
    if (!appleId) return;
    loadScript(APPLE_SRC)
      .then(() => {
        window.AppleID?.auth.init({
          clientId: appleId,
          scope: "name email",
          redirectURI: window.location.origin + "/login",
          usePopup: true,
        });
      })
      .catch(() => onError(t("Apple oturum açma kitaplığı yüklenemedi.")));
  }, [appleId, onError, t]);

  /* Google/Apple penceresi iptal edilir veya FedCM sessizce düşerse düğme
     "bekleniyor" durumunda kilitli kalıyordu. Pencereden dönünce (focus)
     ve en geç 20 sn sonra durum sıfırlanır. */
  useEffect(() => {
    if (busy === null) return;
    const reset = () => setBusy(null);
    window.addEventListener("focus", reset);
    const timer = window.setTimeout(reset, 20_000);
    return () => {
      window.removeEventListener("focus", reset);
      window.clearTimeout(timer);
    };
  }, [busy]);

  const google = useCallback(() => {
    if (!googleReady.current || !window.google) {
      onError(t("Google oturum açma henüz hazır değil."));
      return;
    }
    setBusy("google");
    window.google.accounts.id.prompt((n) => {
      const blocked = n?.isNotDisplayed?.() || n?.isSkippedMoment?.();
      if (!blocked) return;
      setBusy(null);
      const reason = n?.getNotDisplayedReason?.() ?? n?.getSkippedReason?.() ?? "";
      onError(
        reason === "opt_out_or_no_session"
          ? t("Tarayıcıda açık bir Google oturumu yok. Google hesabınıza girip tekrar deneyin.")
          : t("Google penceresi açılamadı. Üçüncü taraf çerezleri engelleniyor olabilir.")
      );
    });
  }, [onError, t]);

  const apple = useCallback(async () => {
    if (!window.AppleID) {
      onError(t("Apple oturum açma henüz hazır değil."));
      return;
    }
    setBusy("apple");
    try {
      const res = await window.AppleID.auth.signIn();
      const token = res?.authorization?.id_token;
      if (token) onToken("apple", token);
      else onError(t("Apple kimlik token'ı alınamadı."));
    } catch {
      onError(t("Apple ile giriş iptal edildi."));
    } finally {
      setBusy(null);
    }
  }, [onToken, onError, t]);

  return (
    <div className="grid gap-[var(--p-space-2)]">
      <button
        type="button"
        className="auth-provider"
        onClick={google}
        disabled={disabled || !googleId || busy !== null}
        title={googleId ? undefined : t("Sunucuda GOOGLE_CLIENT_ID tanımlı değil")}
      >
        <GoogleMark />
        {t(busy === "google" ? "Google bekleniyor…" : "Google ile devam et")}
      </button>

      <button
        type="button"
        className="auth-provider"
        onClick={apple}
        disabled={disabled || !appleId || busy !== null}
        title={appleId ? undefined : t("Sunucuda APPLE_CLIENT_ID tanımlı değil")}
      >
        <AppleMark />
        {t(busy === "apple" ? "Apple bekleniyor…" : "Apple ile devam et")}
      </button>

      {(!googleId || !appleId) && (
        <p className="text-[var(--p-text-3xs)] leading-relaxed text-[var(--ink-faint)]">
          {!googleId && !appleId
            ? t("Google ve Apple girişleri yapılandırılmadı.")
            : !googleId
              ? t("Google girişi yapılandırılmadı.")
              : t("Apple girişi yapılandırılmadı.")}{" "}
          {t("E-posta veya telefon ile devam edin.")}
        </p>
      )}
    </div>
  );
}

function GoogleMark() {
  return (
    <svg viewBox="0 0 18 18" className="size-[18px]" aria-hidden="true">
      <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62Z" />
      <path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.94v2.33A9 9 0 0 0 9 18Z" />
      <path fill="#FBBC05" d="M3.97 10.72a5.4 5.4 0 0 1 0-3.44V4.95H.94a9 9 0 0 0 0 8.1l3.03-2.33Z" />
      <path fill="#EA4335" d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58C13.46.9 11.43 0 9 0A9 9 0 0 0 .94 4.95l3.03 2.33C4.68 5.16 6.66 3.58 9 3.58Z" />
    </svg>
  );
}

function AppleMark() {
  return (
    <svg viewBox="0 0 16 20" className="size-[18px]" aria-hidden="true" fill="currentColor">
      <path d="M13.29 10.6c-.02-2.1 1.71-3.1 1.79-3.15-.97-1.43-2.49-1.63-3.03-1.65-1.29-.13-2.52.76-3.17.76-.66 0-1.66-.74-2.73-.72-1.4.02-2.7.82-3.42 2.07-1.46 2.54-.37 6.29 1.05 8.35.7 1.01 1.53 2.14 2.62 2.1 1.05-.04 1.45-.68 2.72-.68 1.27 0 1.63.68 2.74.66 1.13-.02 1.85-1.03 2.54-2.04.8-1.17 1.13-2.3 1.15-2.36-.03-.01-2.21-.85-2.23-3.34ZM11.2 4.4c.58-.7.97-1.68.86-2.65-.83.03-1.84.55-2.44 1.25-.53.62-1 1.61-.87 2.56.93.07 1.87-.47 2.45-1.16Z" />
    </svg>
  );
}
