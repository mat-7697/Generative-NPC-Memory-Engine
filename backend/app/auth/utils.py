from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import bcrypt
from jose import JWTError, jwt
from app.config import get_settings
from app.models.auth import TokenData

try:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
except Exception:
    pwd_context = None


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    try:
        # Truncate to 72 bytes per standard bcrypt RFC
        pwd_bytes = password.encode("utf-8")[:72]
        return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode("utf-8")
    except Exception:
        if pwd_context:
            return pwd_context.hash(password[:72])
        raise


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        pwd_bytes = plain.encode("utf-8")[:72]
        return bcrypt.checkpw(pwd_bytes, hashed.encode("utf-8"))
    except Exception:
        if pwd_context:
            try:
                return pwd_context.verify(plain[:72], hashed)
            except Exception:
                return False
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Generate a signed JWT access token containing subject data and expiry."""
    settings = get_settings()
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expiration_minutes)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def decode_access_token(token: str) -> TokenData:
    """Decode and validate a JWT access token, extracting player ID, username, and role."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        player_id = payload.get("player_id")
        username: str = payload.get("sub") or payload.get("username")
        role: str = payload.get("role", "player")

        if username is None or player_id is None:
            raise JWTError("Missing essential token claims")

        return TokenData(player_id=int(player_id), username=username, role=role)
    except JWTError as e:
        raise e
