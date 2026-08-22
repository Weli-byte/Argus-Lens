"""Google / Apple OIDC kimlik token doğrulaması.

Sağlayıcının JWKS anahtarlarıyla RS256/ES256 İMZA DOĞRULAMASI yapılır.
İmzası doğrulanmamış, süresi geçmiş, yanlış `aud` veya `iss` taşıyan hiçbir
token kabul edilmez — bunlar kimlik doğrulamanın tamamıdır, atlanamaz.

İstemci kimlikleri ortam değişkeninden okunur:
    GOOGLE_CLIENT_ID   (…apps.googleusercontent.com)
    APPLE_CLIENT_ID    (Services ID, örn. com.arguslens.web)

Tanımlı değilse ilgili sağlayıcı KAPALIDIR ve endpoint 501 döner.
Sahte/atlanmış doğrulama yoktur.
"""

from __future__ import annotations

import os
from typing import Any

import jwt
from jwt import PyJWKClient
from loguru import logger

_GOOGLE_JWKS = "https://www.googleapis.com/oauth2/v3/certs"
_GOOGLE_ISS = {"accounts.google.com", "https://accounts.google.com"}

_APPLE_JWKS = "https://appleid.apple.com/auth/keys"
_APPLE_ISS = {"https://appleid.apple.com"}

_clients: dict[str, PyJWKClient] = {}


def _jwk_client(url: str) -> PyJWKClient:
    if url not in _clients:
        # lifespan: anahtarlar önbelleklenir, her istekte ağa çıkılmaz
        _clients[url] = PyJWKClient(url, cache_keys=True, lifespan=3600)
    return _clients[url]


def google_client_id() -> str:
    return (os.getenv("GOOGLE_CLIENT_ID") or "").strip()


def apple_client_id() -> str:
    return (os.getenv("APPLE_CLIENT_ID") or "").strip()


def providers_status() -> dict[str, dict[str, object]]:
    """Frontend'in hangi düğmeleri etkin göstereceğini bilmesi için.

    İstemci kimliği (client_id) GİZLİ DEĞİLDİR — tasarımı gereği tarayıcıya
    gönderilir. Buradan sunmak, frontend'in `NEXT_PUBLIC_*` derleme zamanı
    değişkenine bağlı kalmasını önler: kimliği yalnızca backend ortamına
    yazıp backend'i yeniden başlatmak yeter, frontend'i yeniden derlemek
    gerekmez. (Gizli olan `client_secret`'tır ve buraya asla konmaz.)
    """
    g, a = google_client_id(), apple_client_id()
    return {
        "google": {"enabled": bool(g), "client_id": g},
        "apple": {"enabled": bool(a), "client_id": a},
    }


class OIDCError(Exception):
    """Doğrulama başarısız — çağıran 401 döndürmeli."""


class OIDCNotConfigured(Exception):
    """Sağlayıcı yapılandırılmamış — çağıran 501 döndürmeli."""


def _verify(
    token: str, *, jwks_url: str, audience: str, issuers: set[str], algorithms: list[str]
) -> dict[str, Any]:
    try:
        signing_key = _jwk_client(jwks_url).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=algorithms,
            audience=audience,
            options={"require": ["exp", "iat", "aud", "iss", "sub"]},
        )
    except jwt.PyJWTError as exc:
        logger.warning("OIDC token doğrulanamadı: {}", exc)
        raise OIDCError("Kimlik token'ı doğrulanamadı.") from exc
    except Exception as exc:  # JWKS ağ hatası vb.
        logger.error("OIDC JWKS hatası: {}", exc)
        raise OIDCError("Kimlik sağlayıcısına ulaşılamadı.") from exc

    if claims.get("iss") not in issuers:
        raise OIDCError("Beklenmeyen token sağlayıcısı.")
    if not claims.get("sub"):
        raise OIDCError("Token'da kullanıcı kimliği yok.")
    return claims


def verify_google(id_token: str) -> dict[str, Any]:
    client_id = google_client_id()
    if not client_id:
        raise OIDCNotConfigured("GOOGLE_CLIENT_ID tanımlı değil.")
    claims = _verify(
        id_token,
        jwks_url=_GOOGLE_JWKS,
        audience=client_id,
        issuers=_GOOGLE_ISS,
        algorithms=["RS256"],
    )
    if claims.get("email") and not claims.get("email_verified", False):
        raise OIDCError("Google hesabının e-postası doğrulanmamış.")
    return {
        "sub": claims["sub"],
        "email": claims.get("email", ""),
        "full_name": claims.get("name", ""),
    }


def verify_apple(id_token: str) -> dict[str, Any]:
    client_id = apple_client_id()
    if not client_id:
        raise OIDCNotConfigured("APPLE_CLIENT_ID tanımlı değil.")
    claims = _verify(
        id_token,
        jwks_url=_APPLE_JWKS,
        audience=client_id,
        issuers=_APPLE_ISS,
        algorithms=["RS256", "ES256"],
    )
    # Apple e-posta doğrulama bayrağını string olarak da gönderebiliyor.
    verified = claims.get("email_verified")
    if claims.get("email") and str(verified).lower() not in ("true", "1"):
        raise OIDCError("Apple hesabının e-postası doğrulanmamış.")
    return {
        "sub": claims["sub"],
        "email": claims.get("email", ""),
        "full_name": "",  # Apple adı yalnızca ilk yetkilendirmede ayrı gönderir
    }
