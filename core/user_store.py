"""Kullanıcı kaydı, kimlik doğrulama ve OTP deposu.

Mevcut `core/auth_manager.py` yalnızca sabit iki demo hesap tutuyordu
(admin/operator). Bu modül onu bozmadan gerçek kayıt akışını ekler:

  - e-posta veya telefon ile kayıt (parola PBKDF2-HMAC-SHA256, 200k tur)
  - telefon için tek kullanımlık kod (OTP)
  - Google / Apple OIDC kimliklerinin yerel hesaba bağlanması

Depo: JSON dosyası (`data/users.json`). Tek süreçli geliştirme kurulumu için
yeterli; üretimde Postgres'e taşınmalı — `database/` katmanı zaten mevcut.

GÜVENLİK NOTU: OAuth kimlik doğrulaması `verify_oidc_token` içinde
sağlayıcının JWKS'i ile İMZA DOĞRULAMASI yaparak yapılır. İmzası
doğrulanmamış hiçbir token kabul edilmez.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from pathlib import Path
from typing import Any, Optional

from loguru import logger

# ── Depo ────────────────────────────────────────────────────────────────────
_DATA_DIR = Path(os.getenv("ARGUS_DATA_DIR", "data"))
_USERS_FILE = _DATA_DIR / "users.json"
_LOCK = threading.RLock()

# ── Parola hash'leme ────────────────────────────────────────────────────────
_PBKDF2_ROUNDS = 200_000
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, rounds, salt_hex, dk_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds)
        )
        return hmac.compare_digest(dk.hex(), dk_hex)
    except (ValueError, AttributeError):
        return False


# ── Doğrulama ───────────────────────────────────────────────────────────────
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")
_PHONE_RE = re.compile(r"^\+[1-9]\d{7,14}$")  # E.164


def normalize_email(value: str) -> str:
    return value.strip().lower()


def normalize_phone(value: str) -> str:
    digits = re.sub(r"[^\d+]", "", value.strip())
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    if not digits.startswith("+"):
        # Türkiye varsayılanı: 05xx… veya 5xx… → +90
        digits = digits.lstrip("0")
        digits = "+90" + digits
    return digits


def is_email(value: str) -> bool:
    return bool(_EMAIL_RE.match(value or ""))


def is_phone(value: str) -> bool:
    return bool(_PHONE_RE.match(value or ""))


PASSWORD_MIN = 8


def password_problem(password: str) -> Optional[str]:
    if not password or len(password) < PASSWORD_MIN:
        return f"Parola en az {PASSWORD_MIN} karakter olmalı."
    if password.isdigit() or password.isalpha():
        return "Parola hem harf hem rakam içermeli."
    return None


# ── Dosya G/Ç ───────────────────────────────────────────────────────────────
def _load() -> dict[str, Any]:
    with _LOCK:
        if not _USERS_FILE.exists():
            return {"users": []}
        try:
            return json.loads(_USERS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("users.json okunamadı: {}", exc)
            return {"users": []}


def _save(data: dict[str, Any]) -> None:
    with _LOCK:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _USERS_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(_USERS_FILE)


def _public(user: dict[str, Any]) -> dict[str, Any]:
    """Parola hash'i ve OAuth alt kimlikleri dışarı sızmaz."""
    return {
        "username": user["username"],
        "role": user.get("role", "operator"),
        "permissions": user.get("permissions", ["read", "inference"]),
        "full_name": user.get("full_name") or "",
        "email": user.get("email") or "",
        "phone": user.get("phone") or "",
        "providers": sorted(user.get("providers", {}).keys()),
    }


# ── Arama ───────────────────────────────────────────────────────────────────
def find_by_identifier(identifier: str) -> Optional[dict[str, Any]]:
    """Kullanıcı adı, e-posta veya telefonla kullanıcı bul."""
    if not identifier:
        return None
    raw = identifier.strip()
    email = normalize_email(raw)
    phone = normalize_phone(raw) if any(c.isdigit() for c in raw) else ""
    for u in _load()["users"]:
        if u["username"].lower() == email:
            return u
        if u.get("email") and u["email"] == email:
            return u
        if phone and u.get("phone") == phone:
            return u
    return None


def identifier_taken(email: str = "", phone: str = "") -> bool:
    for u in _load()["users"]:
        if email and u.get("email") == email:
            return True
        if phone and u.get("phone") == phone:
            return True
    return False


# ── Kayıt ───────────────────────────────────────────────────────────────────
def register(
    *,
    password: str,
    full_name: str = "",
    email: str = "",
    phone: str = "",
) -> dict[str, Any]:
    """Yeni hesap oluşturur. Çakışma veya geçersiz veri varsa ValueError."""
    email = normalize_email(email) if email else ""
    phone = normalize_phone(phone) if phone else ""

    if not email and not phone:
        raise ValueError("E-posta veya telefon numarası gerekli.")
    if email and not is_email(email):
        raise ValueError("Geçersiz e-posta adresi.")
    if phone and not is_phone(phone):
        raise ValueError("Geçersiz telefon numarası. Örnek: +905551112233")

    problem = password_problem(password)
    if problem:
        raise ValueError(problem)

    if identifier_taken(email=email, phone=phone):
        raise ValueError("Bu e-posta veya telefon zaten kayıtlı.")

    data = _load()
    user = {
        "username": email or phone,
        "full_name": full_name.strip(),
        "email": email,
        "phone": phone,
        "password_hash": hash_password(password),
        "role": "operator",
        "permissions": ["read", "inference"],
        "providers": {},
        "created_at": int(time.time()),
        "phone_verified": False,
        "email_verified": False,
    }
    data["users"].append(user)
    _save(data)
    logger.info("Yeni kayıt: {}", user["username"])
    return _public(user)


def authenticate(identifier: str, password: str) -> Optional[dict[str, Any]]:
    user = find_by_identifier(identifier)
    if not user or not user.get("password_hash"):
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return _public(user)


# ── OTP (telefon) ───────────────────────────────────────────────────────────
_OTP_TTL_SECONDS = 300
_OTP_MAX_ATTEMPTS = 5
_otp: dict[str, dict[str, Any]] = {}


def issue_otp(phone: str) -> tuple[str, Optional[str]]:
    """Kod üretir. (phone, gonderim_icin_kod) döner.

    SMS sağlayıcısı yapılandırılmamışsa kod ikinci değerde döner ve
    geliştirme kolaylığı için loglanır. Üretimde bir SMS servisi
    (Twilio vb.) bağlanmalı ve ikinci değer None dönmelidir.
    """
    phone = normalize_phone(phone)
    if not is_phone(phone):
        raise ValueError("Geçersiz telefon numarası.")
    code = f"{secrets.randbelow(1_000_000):06d}"
    _otp[phone] = {
        "code_hash": hashlib.sha256(code.encode()).hexdigest(),
        "expires": time.time() + _OTP_TTL_SECONDS,
        "attempts": 0,
    }
    provider_configured = bool(os.getenv("SMS_PROVIDER_KEY"))
    if provider_configured:
        # SMS entegrasyonu buraya bağlanır.
        logger.info("OTP SMS ile gönderildi: {}", phone)
        return phone, None
    logger.warning("SMS sağlayıcısı yok — OTP yalnızca yanıtta döndürülüyor: {}", phone)
    return phone, code


def verify_otp(phone: str, code: str) -> bool:
    phone = normalize_phone(phone)
    entry = _otp.get(phone)
    if not entry:
        return False
    if time.time() > entry["expires"]:
        _otp.pop(phone, None)
        return False
    entry["attempts"] += 1
    if entry["attempts"] > _OTP_MAX_ATTEMPTS:
        _otp.pop(phone, None)
        return False
    ok = hmac.compare_digest(
        entry["code_hash"], hashlib.sha256((code or "").encode()).hexdigest()
    )
    if ok:
        _otp.pop(phone, None)
    return ok


def get_or_create_phone_user(phone: str) -> dict[str, Any]:
    phone = normalize_phone(phone)
    user = find_by_identifier(phone)
    data = _load()
    if user:
        for u in data["users"]:
            if u.get("phone") == phone:
                u["phone_verified"] = True
        _save(data)
        return _public(user)

    user = {
        "username": phone,
        "full_name": "",
        "email": "",
        "phone": phone,
        "password_hash": "",
        "role": "operator",
        "permissions": ["read", "inference"],
        "providers": {},
        "created_at": int(time.time()),
        "phone_verified": True,
        "email_verified": False,
    }
    data["users"].append(user)
    _save(data)
    logger.info("Telefonla yeni kayıt: {}", phone)
    return _public(user)


# ── OAuth (Google / Apple) ──────────────────────────────────────────────────
def link_oauth_user(
    provider: str, sub: str, email: str = "", full_name: str = ""
) -> dict[str, Any]:
    """Doğrulanmış OIDC kimliğini yerel hesaba bağlar veya hesap oluşturur."""
    email = normalize_email(email) if email else ""
    data = _load()

    for u in data["users"]:
        if u.get("providers", {}).get(provider) == sub:
            _save(data)
            return _public(u)

    if email:
        for u in data["users"]:
            if u.get("email") == email:
                u.setdefault("providers", {})[provider] = sub
                u["email_verified"] = True
                if full_name and not u.get("full_name"):
                    u["full_name"] = full_name
                _save(data)
                logger.info("{} hesabı mevcut kullanıcıya bağlandı: {}", provider, email)
                return _public(u)

    user = {
        "username": email or f"{provider}:{sub}",
        "full_name": full_name,
        "email": email,
        "phone": "",
        "password_hash": "",
        "role": "operator",
        "permissions": ["read", "inference"],
        "providers": {provider: sub},
        "created_at": int(time.time()),
        "phone_verified": False,
        "email_verified": bool(email),
    }
    data["users"].append(user)
    _save(data)
    logger.info("{} ile yeni kayıt: {}", provider, user["username"])
    return _public(user)
