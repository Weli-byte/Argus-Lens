from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from core import oidc, user_store
from core.auth_manager import auth_manager

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str
    expires_in: int = 3600
    user: dict = {}


# Frontend calls: POST /api/v1/auth/token  with JSON {"username": ..., "password": ...}
@router.post("/token", response_model=TokenResponse)
async def login(request: LoginRequest):
    # Önce kayıtlı kullanıcı deposu (e-posta / telefon / kullanıcı adı),
    # sonra yerleşik demo hesapları (admin, operator).
    user = user_store.authenticate(request.username, request.password)
    if not user:
        user = auth_manager.verify_user(request.username, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı adı veya parola hatalı.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth_manager.create_access_token(
        {"sub": user["username"], "role": user["role"]}
    )
    refresh_token = auth_manager.create_refresh_token({"sub": user["username"]})
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user,
    )


# Alias: POST /api/v1/auth/login  (same behaviour)
@router.post("/login", response_model=TokenResponse)
async def login_alias(request: LoginRequest):
    return await login(request)


# Token refresh
@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: RefreshRequest):
    payload = auth_manager.verify_token(request.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    username = payload.get("sub", "")
    access_token = auth_manager.create_access_token({"sub": username})
    refresh_token = auth_manager.create_refresh_token({"sub": username})
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={"username": username},
    )


# ── Kayıt ───────────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    full_name: str = ""
    email: str = ""
    phone: str = ""
    password: str = Field(min_length=user_store.PASSWORD_MIN)


def _tokens_for(user: dict) -> TokenResponse:
    access_token = auth_manager.create_access_token(
        {"sub": user["username"], "role": user["role"]}
    )
    refresh_token = auth_manager.create_refresh_token({"sub": user["username"]})
    return TokenResponse(
        access_token=access_token, refresh_token=refresh_token, user=user
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(request: RegisterRequest):
    """E-posta veya telefon ile hesap açar ve doğrudan oturum başlatır."""
    try:
        user = user_store.register(
            password=request.password,
            full_name=request.full_name,
            email=request.email,
            phone=request.phone,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _tokens_for(user)


# ── Telefon / OTP ───────────────────────────────────────────────────────────
class OtpRequestBody(BaseModel):
    phone: str


class OtpVerifyBody(BaseModel):
    phone: str
    code: str


class OtpRequestResponse(BaseModel):
    phone: str
    sent: bool
    # SMS sağlayıcısı yapılandırılmadığında kod burada döner (yalnız geliştirme).
    dev_code: str | None = None


@router.post("/otp/request", response_model=OtpRequestResponse)
async def otp_request(body: OtpRequestBody):
    try:
        phone, dev_code = user_store.issue_otp(body.phone)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return OtpRequestResponse(phone=phone, sent=True, dev_code=dev_code)


@router.post("/otp/verify", response_model=TokenResponse)
async def otp_verify(body: OtpVerifyBody):
    if not user_store.verify_otp(body.phone, body.code):
        raise HTTPException(status_code=401, detail="Kod hatalı veya süresi dolmuş.")
    user = user_store.get_or_create_phone_user(body.phone)
    return _tokens_for(user)


# ── OAuth (Google / Apple) ──────────────────────────────────────────────────
class OAuthBody(BaseModel):
    id_token: str


@router.get("/providers")
async def providers():
    """Frontend hangi sağlayıcı düğmelerinin etkin olduğunu buradan öğrenir."""
    return oidc.providers_status()


def _oauth_login(provider: str, id_token: str) -> TokenResponse:
    verifier = oidc.verify_google if provider == "google" else oidc.verify_apple
    try:
        identity = verifier(id_token)
    except oidc.OIDCNotConfigured as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except oidc.OIDCError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    user = user_store.link_oauth_user(
        provider,
        identity["sub"],
        email=identity.get("email", ""),
        full_name=identity.get("full_name", ""),
    )
    return _tokens_for(user)


@router.post("/oauth/google", response_model=TokenResponse)
async def oauth_google(body: OAuthBody):
    return _oauth_login("google", body.id_token)


@router.post("/oauth/apple", response_model=TokenResponse)
async def oauth_apple(body: OAuthBody):
    return _oauth_login("apple", body.id_token)
