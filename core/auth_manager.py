import hashlib
import os
from datetime import datetime, timedelta
from typing import Optional

import jwt
from loguru import logger

DEFAULT_USERS = {
    "admin": {
        "password_hash": hashlib.sha256("admin123".encode()).hexdigest(),
        "role": "admin",
        "permissions": ["read", "write", "inference", "manage"],
    },
    "operator": {
        "password_hash": hashlib.sha256("operator123".encode()).hexdigest(),
        "role": "operator",
        "permissions": ["read", "inference"],
    },
}

SECRET_KEY = os.getenv("SECRET_KEY", "argus-super-secret-key-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 7


class AuthManager:
    def verify_user(self, username: str, password: str) -> Optional[dict]:
        if username not in DEFAULT_USERS:
            return None
        user = DEFAULT_USERS[username]
        if user["password_hash"] != hashlib.sha256(password.encode()).hexdigest():
            return None
        return {
            "username": username,
            "role": user["role"],
            "permissions": user["permissions"],
        }

    def create_access_token(self, data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire, "type": "access"})
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    def create_refresh_token(self, data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    def verify_token(self, token: str) -> Optional[dict]:
        try:
            return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.JWTError as e:
            logger.error("Token error: {}", e)
            return None


auth_manager = AuthManager()
