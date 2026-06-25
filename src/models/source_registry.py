from sqlalchemy import (
    String,
    ForeignKey,
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from src.db.base import Base
from src.models.mixins import TimestampMixin
from src.utils.uuid_utils import generate_uuid


class SourceRegistry(Base, TimestampMixin):
    __tablename__ = "source_registry"

    id: Mapped[str] = mapped_column(
        primary_key=True,
        default=generate_uuid,
    )

    professional_id: Mapped[str] = mapped_column(
        ForeignKey("professional_profile.id")
    )

    source_type: Mapped[str]
    source_url: Mapped[str]