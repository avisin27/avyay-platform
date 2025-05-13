import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

def get_db_connection():
    """Establish and return a secure PostgreSQL database connection."""
    try:
        conn = psycopg2.connect(
            host=os.environ["DB_HOST"],
            database=os.environ["DB_NAME"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASS"],
            port=os.environ["DB_PORT"],
        )
        return conn
    except Exception as e:
        raise RuntimeError(f"Database connection failed: {e}")
