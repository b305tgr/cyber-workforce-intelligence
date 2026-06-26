from pydantic import BaseModel, ConfigDict


class ProfessionalCreate(BaseModel):
    full_name: str
    current_title: str | None = None
    years_experience: int | None = None
    current_company_id: str | None = None
    location_id: str | None = None


class ProfessionalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    full_name: str
    current_title: str | None = None
    years_experience: int | None = None
    current_company_id: str | None = None
    location_id: str | None = None