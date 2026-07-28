from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class FavoriteSpot(Base):
    __tablename__ = "favorite_spots"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    spot_id: Mapped[int] = mapped_column(ForeignKey("spots.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="favorite_spots")
    spot: Mapped["Spot"] = relationship(back_populates="favorited_by")
