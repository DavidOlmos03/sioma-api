from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional

from src.core.config import settings

ALGORITHM = "HS256"

def create_device_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
        to_encode.update({"exp": expire})
    
    # Per requirements, tokens do not expire by default
    to_encode.update({"iat": datetime.utcnow()})
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str, credentials_exception):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        tenant_id: str = payload.get("tenant_id")
        device_id: str = payload.get("device_id")
        if tenant_id is None or device_id is None:
            raise credentials_exception
        return payload
    except JWTError:
        raise credentials_exception
