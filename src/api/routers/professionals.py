from fastapi import APIRouter

from src.db.session import SessionLocal
from src.services.professional_service import ProfessionalService

router = APIRouter(
    prefix="/professionals",
    tags=["Professionals"],
)


@router.get("/")
def get_professionals():

    db = SessionLocal()

    try:

        service = ProfessionalService(db)

        return service.get_all_professionals()

    finally:

        db.close()