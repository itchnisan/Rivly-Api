from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.species import Species
    from app.models.spot import Spot
    from app.models.user import User


class Catch(Base):
    __tablename__ = "catches"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    spot_id: Mapped[int] = mapped_column(ForeignKey("spots.id"), nullable=False)
    species_id: Mapped[int] = mapped_column(ForeignKey("species.id"), nullable=False)
    weight_g: Mapped[int | None] = mapped_column(Integer, nullable=True)
    length_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    caught_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    conditions: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="catches")
    spot: Mapped["Spot"] = relationship(back_populates="catches")
    species: Mapped["Species"] = relationship(back_populates="catches")
