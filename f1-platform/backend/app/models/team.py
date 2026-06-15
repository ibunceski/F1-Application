from typing import Optional

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    short_name: Mapped[str] = mapped_column(String, nullable=False)
    nationality: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    constructor_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    def __repr__(self) -> str:
        return f"Team(id={self.id!r}, name={self.name!r})"
