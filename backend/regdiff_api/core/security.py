"""Password hashing (bcrypt) and JWT tokens (SEC-1)."""

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from regdiff_common.config import get_settings

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def create_token(user_id: int, role: str) -> tuple[str, int]:
    settings = get_settings()
    expires_in = settings.jwt_expiry_minutes * 60
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": datetime.now(UTC) + timedelta(seconds=expires_in),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM), expires_in


def decode_token(token: str) -> dict:
    """Raises jwt.PyJWTError when the token is invalid or expired."""
    return jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM])
