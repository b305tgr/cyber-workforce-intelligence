from sqlalchemy import (
    Table,
    Column,
    ForeignKey,
    UniqueConstraint,
)

from src.db.base import Base


profile_skill = Table(
    "profile_skill",
    Base.metadata,
    Column(
        "professional_id",
        ForeignKey("professional_profile.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "skill_id",
        ForeignKey("skill.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    UniqueConstraint(
        "professional_id",
        "skill_id",
        name="uq_profile_skill",
    ),
)


profile_certification = Table(
    "profile_certification",
    Base.metadata,
    Column(
        "professional_id",
        ForeignKey("professional_profile.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "certification_id",
        ForeignKey("certification.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    UniqueConstraint(
        "professional_id",
        "certification_id",
        name="uq_profile_certification",
    ),
)


company_industry = Table(
    "company_industry",
    Base.metadata,
    Column(
        "company_id",
        ForeignKey("company.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "industry_id",
        ForeignKey("industry.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    UniqueConstraint(
        "company_id",
        "industry_id",
        name="uq_company_industry",
    ),
)