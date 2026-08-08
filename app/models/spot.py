import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.catch import Catch
    from app.models.favorite_spot import FavoriteSpot
    from app.models.user import User


class WaterType(str, enum.Enum):
    RIVER = "river"
    LAKE = "lake"
    POND = "pond"


class Spot(Base):
    __tablename__ = "spots"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    water_type: Mapped[WaterType] = mapped_column(Enum(WaterType, name="water_type"), nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    creator: Mapped["User"] = relationship(back_populates="spots")
    catches: Mapped[list["Catch"]] = relationship(back_populates="spot")
    favorited_by: Mapped[list["FavoriteSpot"]] = relationship(back_populates="spot")
