"""
One-off script: creates the nodes/edges tables in PostGIS. Run once after
starting a fresh database container.
"""

from sqlalchemy import create_engine
from yorimichi.infrastructure.postgis_models import Base

DATABASE_URL = "postgresql://postgres:yourpassword@localhost:5432/yorimichi"

engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)
print("Tables created successfully.")