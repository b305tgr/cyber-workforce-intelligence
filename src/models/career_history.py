from sqlalchemy import (
    String,
    Integer,
    ForeignKey,
)
from sqlalchemy import Index
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from src.db.base import Base
from src.models.mixins import TimestampMixin
from src.utils.uuid_utils import generate_uuid


class CareerHistory(Base, TimestampMixin):
    __tablename__ = "career_history"
    __table_args__ = (
    Index(
        "idx_role_title",
        "role_title",
    ),
)

    id: Mapped[str] = mapped_column(
        primary_key=True,
        default=generate_uuid,
    )

    professional_id: Mapped[str] = mapped_column(
        ForeignKey("professional_profile.id")
    )

    company_id: Mapped[str | None] = mapped_column(
        ForeignKey("company.id")
    )

    role_title: Mapped[str | None]
    start_year: Mapped[int | None]
    end_year: Mapped[int | None]

    professional = relationship(
        "ProfessionalProfile"
    )

    company = relationship(
        "Company"
    )