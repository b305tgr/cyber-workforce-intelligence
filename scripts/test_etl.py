from src.db.session import SessionLocal
from src.etl.importers.professional_importer import (
    ProfessionalImporter,
)

db = SessionLocal()

try:

    importer = ProfessionalImporter(db)

    result = importer.import_csv(
        "data/sample/professionals.csv"
    )

    print(result)

finally:

    db.close()