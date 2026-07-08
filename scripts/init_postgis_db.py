"""
One-off script: creates the nodes/edges tables in PostGIS. Run once after
starting a fresh database container.
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from yorimichi.infrastructure.postgis_models import Base

load_dotenv()

DATABASE_URL = os.environ.get("POSTGIS_DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "POSTGIS_DATABASE_URL is not set. Set it in your .env file or environment."
    )

engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)
print("Tables created successfully.")