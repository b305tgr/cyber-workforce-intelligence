from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.company import Company
from src.models.professional_profile import ProfessionalProfile
from src.models.import_history import ImportHistory
from src.models.reference import (
    Skill,
    Certification,
)

from src.schemas.dashboard_schema import (
    DashboardSummary,
    TopSkillResponse,
)


class DashboardService:

    def __init__(self, db: Session):

        self.db = db

    def get_summary(self) -> DashboardSummary:

        professionals = (
            self.db.query(
                func.count(ProfessionalProfile.id)
            )
            .scalar()
        )

        companies = (
            self.db.query(
                func.count(Company.id)
            )
            .scalar()
        )

        skills = (
            self.db.query(
                func.count(Skill.id)
            )
            .scalar()
        )

        certifications = (
            self.db.query(
                func.count(Certification.id)
            )
            .scalar()
        )

        imports = (
            self.db.query(
                func.count(ImportHistory.id)
            )
            .scalar()
        )

        return DashboardSummary(
            professionals=professionals,
            companies=companies,
            skills=skills,
            certifications=certifications,
            imports=imports,
        )

    def get_top_skills(
        self,
        limit: int = 10,
    ):

        rows = (
            self.db.query(
                Skill.name,
                func.count(
                    ProfessionalProfile.id
                ).label("count"),
            )
            .join(
                Skill.professionals
            )
            .group_by(
                Skill.id,
                Skill.name,
            )
            .order_by(
                func.count(
                    ProfessionalProfile.id
                ).desc()
            )
            .limit(limit)
            .all()
        )

        return [
            TopSkillResponse(
                skill=row.name,
                count=row.count,
            )
            for row in rows
        ]