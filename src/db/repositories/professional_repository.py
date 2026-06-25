from sqlalchemy.orm import Session

from src.models.professional_profile import (
    ProfessionalProfile,
)


class ProfessionalRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, profile_id: str):
        return (
            self.db.query(ProfessionalProfile)
            .filter(
                ProfessionalProfile.id == profile_id
            )
            .first()
        )

    def get_by_name(self, name: str):
        return (
            self.db.query(ProfessionalProfile)
            .filter(
                ProfessionalProfile.full_name.ilike(
                    f"%{name}%"
                )
            )
            .all()
        )