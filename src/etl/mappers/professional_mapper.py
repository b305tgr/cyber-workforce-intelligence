from src.schemas.professional_schema import ProfessionalCreate


class ProfessionalMapper:

    def map(self, record):

        return ProfessionalCreate(
            full_name=record.full_name,
            current_title=record.current_title,
            years_experience=record.years_experience,
        )