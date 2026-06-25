from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base
from src.models.mixins import TimestampMixin
from src.utils.uuid_utils import generate_uuid


class Company(Base, TimestampMixin):
    __tablename__ = "company"

    id: Mapped[str] = mapped_column(
        primary_key=True,
        default=generate_uuid,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )

    website: Mapped[str | None] = mapped_column(
        String(500)
    )

    location_id: Mapped[str | None] = mapped_column(
        ForeignKey("location.id")
    )

    location = relationship("Location")