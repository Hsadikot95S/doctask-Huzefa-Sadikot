import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


load_dotenv()


def test_database_connection():
    database_url = os.getenv("DATABASE_URL")

    assert database_url, "DATABASE_URL is not configured"

    engine = create_engine(database_url)

    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        assert result.scalar() == 1