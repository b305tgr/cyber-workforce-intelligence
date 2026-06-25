from datetime import date
from sqlalchemy import (
    String,
    ForeignKey,
    Index,
)
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

from src.models.associations import (
    profile_skill,
    profile_certification,
)
class ProfessionalProfile(Base, TimestampMixin):
    __tablename__ = "professional_profile"
    __table_args__ = (
        Index(
            "idx_professional_name",
            "full_name",
        ),
    )

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

    skills = relationship(
        "Skill",
        secondary=profile_skill,
        back_populates="professionals",
    )

    certifications = relationship(
        "Certification",
        secondary=profile_certification,
        back_populates="professionals",
    )