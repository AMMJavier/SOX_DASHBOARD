"""JWT y bcrypt interoperable con hashes bcrypt previos de passlib."""
import os
import bcrypt
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from jose import jwt

load_dotenv()
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
if ALGORITHM not in {"HS256", "HS384", "HS512"}:
    raise RuntimeError("JWT_ALGORITHM no permitido para claves HMAC")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))

def _get_secret():
    secret = os.getenv("JWT_SECRET_KEY")
    if not secret or len(secret) < 32 or secret.startswith("REEMPLAZAR"):
        raise RuntimeError("JWT_SECRET_KEY debe contener al menos 32 caracteres aleatorios")
    return secret

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.strip().encode("ascii"))
    except (ValueError, TypeError, UnicodeError):
        return False

def get_password_hash(password: str) -> str:
    raw = password.encode("utf-8")
    if not 8 <= len(raw) <= 72:
        raise ValueError("Contraseña fuera del rango de 8 a 72 bytes")
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("ascii")

def create_access_token(data: dict) -> str:
    now = datetime.now(timezone.utc)
    payload = {**data, "iat": now, "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)}
    return jwt.encode(payload, _get_secret(), algorithm=ALGORITHM)

def decode_access_token(token: str) -> dict:
    return jwt.decode(token, _get_secret(), algorithms=[ALGORITHM], options={"require_exp": True})
