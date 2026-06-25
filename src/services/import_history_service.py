from sqlalchemy.orm import Session

from src.models.import_history import ImportHistory


class ImportHistoryService:

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        file_name: str,
        import_type: str,
        total: int,
        inserted: int,
        duplicates: int,
        errors: int,
        status: str,
    ):

        history = ImportHistory(
            file_name=file_name,
            import_type=import_type,
            total_records=total,
            inserted_records=inserted,
            duplicate_records=duplicates,
            error_records=errors,
            status=status,
        )

        self.db.add(history)
        self.db.commit()
        self.db.refresh(history)

        return history