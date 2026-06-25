from sqlalchemy import (
    String,
    Integer,
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


class Education(Base, TimestampMixin):
    __tablename__ = "education"

    id: Mapped[str] = mapped_column(
        primary_key=True,
        default=generate_uuid,
    )

    professional_id: Mapped[str] = mapped_column(
        ForeignKey("professional_profile.id")
    )

    institution: Mapped[str | None]
    degree: Mapped[str | None]
    graduation_year: Mapped[int | None]

    professional = relationship(
        "ProfessionalProfile"
    )