from datetime import datetime, timedelta, timezone

from jose import jwt

from passlib.context import CryptContext

from fastapi import HTTPException, status, Depends

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import settings


pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


bearer = HTTPBearer()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )

    return jwt.encode(
        {
            "sub": str(user_id),
            "exp": expire
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm
    )


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer)
) -> int:

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm]
        )

        return int(payload["sub"])

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        ) from exc