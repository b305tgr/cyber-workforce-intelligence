from sqlalchemy import (
    String,
    Float,
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


class SourceRegistry(
    Base,
    TimestampMixin,
):
    __tablename__ = "source_registry"

    id: Mapped[str] = mapped_column(
        primary_key=True,
        default=generate_uuid,
    )

    professional_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "professional_profile.id"
        ),
        nullable=True,
    )

    source_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    source_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    confidence_score: Mapped[float] = mapped_column(
        Float,
        default=1.0,
    )

    collector_version: Mapped[str | None] = mapped_column(
        String(50)
    )

    professional = relationship(
        "ProfessionalProfile"
    )