from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.dependencies import get_db
from src.schemas.dashboard_schema import (
    DashboardSummary,
    TopSkillResponse,
)
from src.services.dashboard_service import (
    DashboardService,
)

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)


@router.get(
    "/summary",
    response_model=DashboardSummary,
)
def get_dashboard_summary(
    db: Session = Depends(get_db),
):

    service = DashboardService(db)

    return service.get_summary()


@router.get(
    "/top-skills",
    response_model=list[TopSkillResponse],
)
def get_top_skills(
    db: Session = Depends(get_db),
):

    service = DashboardService(db)

    return service.get_top_skills()