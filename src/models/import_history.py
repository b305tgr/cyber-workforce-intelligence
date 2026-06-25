from sqlalchemy import String, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from src.db.base import Base
from src.utils.uuid_utils import generate_uuid


class ImportHistory(Base):

    __tablename__ = "import_history"

    id: Mapped[str] = mapped_column(
        primary_key=True,
        default=generate_uuid,
    )

    file_name: Mapped[str] = mapped_column(
        String(255)
    )

    import_type: Mapped[str] = mapped_column(
        String(50)
    )

    total_records: Mapped[int]

    inserted_records: Mapped[int]

    duplicate_records: Mapped[int]

    error_records: Mapped[int]

    status: Mapped[str] = mapped_column(
        String(20)
    )

    imported_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )