from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, Float, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.catch import Catch


class Species(Base):
    __tablename__ = "species"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    common_name: Mapped[str] = mapped_column(String(150), nullable=False)
    legal_size_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    open_season_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    open_season_end: Mapped[date | None] = mapped_column(Date, nullable=True)

    catches: Mapped[list["Catch"]] = relationship(back_populates="species")
