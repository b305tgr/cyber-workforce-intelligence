from src.db.session import SessionLocal
from src.services.source_registry_service import (
    SourceRegistryService,
)

db = SessionLocal()

try:
    service = SourceRegistryService(db)

    source = service.create_source(
        source_type="manual_research",
        source_url="https://example.com",
        confidence_score=0.95,
        collector_version="v1",
    )

    print("Created Source")

    print("ID:", source.id)
    print("Type:", source.source_type)
    print("URL:", source.source_url)
    print("Confidence:", source.confidence_score)

finally:
    db.close()