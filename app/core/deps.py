from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.services import user_service
from app.services.weather_service import OpenMeteoProvider, WeatherProvider

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# Instance unique : le cache mémoire des prévisions doit survivre aux requêtes.
_weather_provider = OpenMeteoProvider()


def get_weather_provider() -> WeatherProvider:
    return _weather_provider


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except Exception as exc:
        raise credentials_exception from exc

    user = await user_service.get_user_by_id(db, int(user_id))
    if user is None:
        raise credentials_exception
    return user
