from datetime import datetime

from pydantic import BaseModel


class ImportHistoryResponse(BaseModel):

    id: str
    file_name: str
    import_type: str

    total_records: int
    inserted_records: int
    duplicate_records: int
    error_records: int

    status: str

    imported_at: datetime

    class Config:
        from_attributes = True