from sqlalchemy.orm import Session

from src.models.professional_profile import ProfessionalProfile


class ProfessionalRepository:

    def __init__(self, db: Session):
        self.db = db

    def add(self, professional: ProfessionalProfile):
        self.db.add(professional)
        self.db.commit()
        self.db.refresh(professional)
        return professional

    def find_by_name(self, full_name: str):

        return (
            self.db.query(ProfessionalProfile)
            .filter(
                ProfessionalProfile.full_name == full_name
            )
            .first()
        )

    def list_all(self):

        return (
            self.db.query(ProfessionalProfile)
            .all()
        )