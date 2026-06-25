from pydantic import BaseModel, Field


class ProfessionalRecord(BaseModel):
    full_name: str = Field(min_length=2)
    current_title: str | None = None
    years_experience: int | None = None