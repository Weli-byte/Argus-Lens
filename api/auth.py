from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

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
    user = auth_manager.verify_user(request.username, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth_manager.create_access_token(
        {"sub": user["username"], "role": user["role"]}
    )
    refresh_token = auth_manager.create_refresh_token({"sub": user["username"]})
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={"username": user["username"], "role": user["role"]},
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
