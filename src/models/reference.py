from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.utils.uuid_utils import generate_uuid


class Industry(Base):
    __tablename__ = "industry"

    id: Mapped[str] = mapped_column(
        primary_key=True,
        default=generate_uuid,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )


class Certification(Base):
    __tablename__ = "certification"

    id: Mapped[str] = mapped_column(
        primary_key=True,
        default=generate_uuid,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )


class Skill(Base):
    __tablename__ = "skill"

    id: Mapped[str] = mapped_column(
        primary_key=True,
        default=generate_uuid,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )


class Role(Base):
    __tablename__ = "role"

    id: Mapped[str] = mapped_column(
        primary_key=True,
        default=generate_uuid,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )