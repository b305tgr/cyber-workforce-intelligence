from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.models.mixins import TimestampMixin
from src.utils.uuid_utils import generate_uuid


class Location(Base, TimestampMixin):
    __tablename__ = "location"

    id: Mapped[str] = mapped_column(
        primary_key=True,
        default=generate_uuid,
    )

    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(100))