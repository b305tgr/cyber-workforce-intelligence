from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.dependencies import get_db
from src.schemas.import_schema import (
    ImportHistoryResponse,
)
from src.services.import_history_service import (
    ImportHistoryService,
)

router = APIRouter(
    prefix="/imports",
    tags=["Imports"],
)


@router.get(
    "/history",
    response_model=list[ImportHistoryResponse],
)
def get_import_history(
    db: Session = Depends(get_db),
):

    service = ImportHistoryService(db)

    return service.list_all()