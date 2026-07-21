import json
from datetime import datetime, timedelta

from passlib.context import CryptContext
import jwt
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.config import get_settings
from app.database import get_db
from app.models import User

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Redis: connect lazily so the app doesn't crash if Redis is offline
_redis_client = None

def _get_redis():
    global _redis_client
    if _redis_client is None:
        try:
            import redis as _redis_mod
            _redis_client = _redis_mod.from_url(settings.redis_url, decode_responses=True)
            _redis_client.ping()  # test connection
        except Exception:
            _redis_client = None
    return _redis_client


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

# In-memory session store as fallback when Redis is unavailable
_memory_sessions: dict[str, str] = {}

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expiration_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm="HS256")
    
    session_id = str(data.get("sub"))
    rc = _get_redis()
    if rc:
        try:
            rc.set(f"session:{session_id}", encoded_jwt, ex=int(settings.jwt_expiration_minutes * 60))
        except Exception:
            _memory_sessions[session_id] = encoded_jwt
    else:
        _memory_sessions[session_id] = encoded_jwt
    return encoded_jwt

def logout_user(user_id: str):
    rc = _get_redis()
    if rc:
        try:
            rc.delete(f"session:{user_id}")
        except Exception:
            _memory_sessions.pop(str(user_id), None)
    else:
        _memory_sessions.pop(str(user_id), None)

def get_token_from_cookie(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        # Also allow Bearer token for flexibility (e.g. testing)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token

def get_current_user(token: str = Depends(get_token_from_cookie), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception

    # Check if session exists in Redis or memory fallback
    session_id = str(user_id)
    rc = _get_redis()
    if rc:
        try:
            active_token = rc.get(f"session:{session_id}")
            if not active_token or active_token != token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session expired or invalid",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        except HTTPException:
            raise
        except Exception:
            # Redis down, fall through to memory check
            if _memory_sessions.get(session_id) != token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session expired or invalid",
                    headers={"WWW-Authenticate": "Bearer"},
                )
    else:
        if session_id in _memory_sessions and _memory_sessions[session_id] != token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired or invalid",
                headers={"WWW-Authenticate": "Bearer"},
            )

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user
