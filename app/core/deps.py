from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.services import user_service
from app.services.geocoding_service import BanGeocodingProvider, GeocodingProvider
from app.services.overpass_service import OverpassProvider, WaterTypeProvider
from app.services.weather_service import OpenMeteoProvider, WeatherProvider


class BearerAuth(HTTPBearer):
    """HTTPBearer renvoie 403 par défaut quand l'en-tête est absent ; on veut 401."""

    async def __call__(self, request: Request) -> HTTPAuthorizationCredentials:
        try:
            return await super().__call__(request)
        except HTTPException as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=exc.detail,
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc


bearer_scheme = BearerAuth()

# Instance unique : le cache mémoire des prévisions doit survivre aux requêtes.
_weather_provider = OpenMeteoProvider()


def get_weather_provider() -> WeatherProvider:
    return _weather_provider


# Instance unique : le cache mémoire des détections doit survivre aux requêtes.
_water_type_provider = OverpassProvider()


def get_water_type_provider() -> WaterTypeProvider:
    return _water_type_provider


# Instance unique : le cache mémoire des recherches doit survivre aux requêtes.
_geocoding_provider = BanGeocodingProvider()


def get_geocoding_provider() -> GeocodingProvider:
    return _geocoding_provider


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except Exception as exc:
        raise credentials_exception from exc

    user = await user_service.get_user_by_id(db, int(user_id))
    if user is None:
        raise credentials_exception
    return user
