import os

DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://admin:secretpassword@localhost:5432/pepebot_db"
)