from src.db.session import SessionLocal
from src.models.reference import (
    Role,
    Skill,
    Certification,
    Industry,
)

from src.seeds.reference_data.roles import ROLES
from src.seeds.reference_data.skills import SKILLS
from src.seeds.reference_data.certifications import (
    CERTIFICATIONS,
)
from src.seeds.reference_data.industries import (
    INDUSTRIES,
)


db = SessionLocal()


def seed(model, values):
    for value in values:
        exists = (
            db.query(model)
            .filter(model.name == value)
            .first()
        )

        if not exists:
            db.add(model(name=value))

    db.commit()


try:
    seed(Role, ROLES)
    seed(Skill, SKILLS)
    seed(Certification, CERTIFICATIONS)
    seed(Industry, INDUSTRIES)

    print("Reference data seeded.")
finally:
    db.close()