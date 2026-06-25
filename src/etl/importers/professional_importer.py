from src.etl.parsers.csv_parser import CSVParser
from src.etl.validators.professional_validator import ProfessionalValidator
from src.etl.mappers.professional_mapper import ProfessionalMapper
from src.etl.models.import_result import ImportResult

from src.services.professional_service import ProfessionalService
from src.services.dedup_service import DedupService

from src.core.logger import logger
from pathlib import Path

from src.services.import_history_service import (
    ImportHistoryService,
)

class ProfessionalImporter:

    def __init__(self, db):

        self.db = db

        self.parser = CSVParser()

        self.validator = ProfessionalValidator()

        self.mapper = ProfessionalMapper()

        self.professional_service = ProfessionalService(db)

        self.dedup_service = DedupService(db)
        self.history_service = ImportHistoryService(db)

    def import_csv(self, file_path: str):

        rows = self.parser.parse(file_path)

        inserted = 0
        duplicates = 0
        errors = 0

        for row in rows:

            try:

                validated = self.validator.validate(row)

                existing = self.dedup_service.find_by_name(
                    validated.full_name
                )

                if existing:
                    duplicates += 1
                    continue

                payload = self.mapper.map(validated)

                self.professional_service.create_professional(
                    payload
                )

                inserted += 1

            except Exception as ex:

                logger.exception(ex)

                errors += 1

        result = ImportResult(
            total=len(rows),
            inserted=inserted,
            duplicates=duplicates,
            errors=errors,
        )

        self.history_service.create(
            file_name=Path(file_path).name,
            import_type="CSV",
            total=result.total,
            inserted=result.inserted,
            duplicates=result.duplicates,
            errors=result.errors,
            status="SUCCESS" if result.errors == 0 else "PARTIAL",
        )

        return result
