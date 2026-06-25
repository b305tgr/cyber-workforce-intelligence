from pydantic import BaseModel


class ProfessionalCreate(BaseModel):
    full_name: str
    current_title: str | None = None
    years_experience: int | None = None
    current_company_id: str | None = None
    location_id: str | None = None