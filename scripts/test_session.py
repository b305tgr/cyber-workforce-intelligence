from src.db.session import SessionLocal


db = SessionLocal()

try:
    print(
        "Database session created successfully."
    )
finally:
    db.close()
    print(
        "Database session closed."
    )