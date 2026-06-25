from src.db.session import SessionLocal
from src.schemas.professional_schema import (
    ProfessionalCreate,
)
from src.services.professional_service import (
    ProfessionalService,
)

db = SessionLocal()

try:
    service = ProfessionalService(db)

    professional = service.create_professional(
        ProfessionalCreate(
            full_name="John Doe",
            current_title="SOC Analyst",
            years_experience=5,
        )
    )

    print("Professional Created")
    print("ID:", professional.id)
    print("Name:", professional.full_name)
    print("Title:", professional.current_title)

finally:
    db.close()