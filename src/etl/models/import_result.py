from pydantic import BaseModel


class ImportResult(BaseModel):
    total: int
    inserted: int
    duplicates: int
    errors: int