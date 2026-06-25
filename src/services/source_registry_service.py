from sqlalchemy.orm import Session

from src.models.source_registry import (
    SourceRegistry,
)


class SourceRegistryService:
    def __init__(self, db: Session):
        self.db = db

    def create_source(
        self,
        source_type: str,
        source_url: str | None = None,
        professional_id: str | None = None,
        confidence_score: float = 1.0,
        collector_version: str | None = None,
    ):
        source = SourceRegistry(
            professional_id=professional_id,
            source_type=source_type,
            source_url=source_url,
            confidence_score=confidence_score,
            collector_version=collector_version,
        )

        self.db.add(source)
        self.db.commit()
        self.db.refresh(source)

        return source

    def get_by_id(
        self,
        source_id: str,
    ):
        return (
            self.db.query(SourceRegistry)
            .filter(
                SourceRegistry.id == source_id
            )
            .first()
        )