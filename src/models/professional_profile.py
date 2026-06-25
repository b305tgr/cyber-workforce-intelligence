from datetime import date

from sqlalchemy import (
    String,
    Date,
    ForeignKey,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from src.db.base import Base
from src.models.mixins import TimestampMixin
from src.utils.uuid_utils import generate_uuid


class ProfessionalProfile(Base, TimestampMixin):
    __tablename__ = "professional_profile"

    id: Mapped[str] = mapped_column(
        primary_key=True,
        default=generate_uuid,
    )

    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    current_title: Mapped[str | None] = mapped_column(
        String(255)
    )

    years_experience: Mapped[int | None]

    current_company_id: Mapped[str | None] = mapped_column(
        ForeignKey("company.id")
    )

    location_id: Mapped[str | None] = mapped_column(
        ForeignKey("location.id")
    )

    current_company = relationship("Company")
    location = relationship("Location")