from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.dependencies import get_db
from src.schemas.professional_schema import (
    ProfessionalCreate,
    ProfessionalResponse,
)
from src.services.professional_service import (
    ProfessionalService,
)

router = APIRouter(
    prefix="/professionals",
    tags=["Professionals"],
)


@router.get("/")
def get_professionals(
    db: Session = Depends(get_db),
):

    service = ProfessionalService(db)

    return service.get_all_professionals()


@router.post(
    "/",
    response_model=ProfessionalResponse,
    status_code=201,
)
def create_professional(
    payload: ProfessionalCreate,
    db: Session = Depends(get_db),
):

    service = ProfessionalService(db)

    return service.create_professional(payload)


@router.get(
    "/{professional_id}",
    response_model=ProfessionalResponse,
)
def get_professional(
    professional_id: str,
    db: Session = Depends(get_db),
):

    service = ProfessionalService(db)

    professional = service.get_professional_by_id(
        professional_id
    )

    if professional is None:
        raise HTTPException(
            status_code=404,
            detail="Professional not found",
        )

    return professional


@router.put(
    "/{professional_id}",
    response_model=ProfessionalResponse,
)
def update_professional(
    professional_id: str,
    payload: ProfessionalCreate,
    db: Session = Depends(get_db),
):

    service = ProfessionalService(db)

    professional = service.update_professional(
        professional_id,
        payload,
    )

    if professional is None:
        raise HTTPException(
            status_code=404,
            detail="Professional not found",
        )

    return professional