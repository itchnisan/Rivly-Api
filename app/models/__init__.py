from app.models.base import Base
from app.models.user import User
from app.models.spot import Spot, WaterType
from app.models.species import Species
from app.models.catch import Catch
from app.models.favorite_spot import FavoriteSpot

__all__ = [
    "Base",
    "User",
    "Spot",
    "WaterType",
    "Species",
    "Catch",
    "FavoriteSpot",
]
