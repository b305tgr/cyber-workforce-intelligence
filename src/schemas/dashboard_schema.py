from pydantic import BaseModel


class DashboardSummary(BaseModel):
    professionals: int
    companies: int
    skills: int
    certifications: int
    imports: int


class TopSkillResponse(BaseModel):
    skill: str
    count: int