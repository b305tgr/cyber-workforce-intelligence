from sqlalchemy import func

from src.models.professional_profile import (
    ProfessionalProfile,
)


class DedupService:
    def __init__(self, db):
        self.db = db

    def find_by_name(
        self,
        full_name: str,
    ):
        return (
            self.db.query(
                ProfessionalProfile
            )
            .filter(
                func.lower(
                    ProfessionalProfile.full_name
                )
                == full_name.lower()
            )
            .first()
        )