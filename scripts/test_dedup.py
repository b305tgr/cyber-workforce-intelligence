from src.db.session import SessionLocal
from src.services.dedup_service import (
    DedupService,
)

db = SessionLocal()

try:
    service = DedupService(db)

    professional = service.find_by_name(
        "john doe"
    )

    if professional:
        print(
            "Duplicate found:"
        )
        print(
            professional.id
        )
        print(
            professional.full_name
        )
    else:
        print(
            "No duplicate found."
        )

finally:
    db.close()