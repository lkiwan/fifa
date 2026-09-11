import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/fifa",
)

DAILY_SCRAPE_HOUR = int(os.getenv("DAILY_SCRAPE_HOUR", "22"))
DAILY_SCRAPE_MINUTE = int(os.getenv("DAILY_SCRAPE_MINUTE", "0"))
PORTRAIT_SIZE = os.getenv("PORTRAIT_SIZE", "big")