from sqlalchemy.orm import Session

from src.db.repositories.professional_repository import (
    ProfessionalRepository,
)

from src.models.professional_profile import (
    ProfessionalProfile,
)

from src.schemas.professional_schema import (
    ProfessionalCreate,
)


class ProfessionalService:

    def __init__(self, db: Session):

        self.repository = ProfessionalRepository(db)

    def create_professional(
        self,
        payload: ProfessionalCreate,
    ):

        professional = ProfessionalProfile(
            full_name=payload.full_name,
            current_title=payload.current_title,
            years_experience=payload.years_experience,
            current_company_id=payload.current_company_id,
            location_id=payload.location_id,
        )

        return self.repository.add(professional)

    def get_all_professionals(self):

        return self.repository.list_all()