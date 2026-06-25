from sqlalchemy import create_engine

engine = create_engine(
    "postgresql+psycopg2://postgres:postgres@localhost:5432/cyber_workforce"
)

with engine.connect() as conn:
    print("Database connection successful.")