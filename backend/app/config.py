import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

# postgresql+psycopg://user:pass@10.10.10.13:5432/company_brain in production (LXC 3).
# SQLite is only for local development and tests.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./company_brain_dev.db")

SUPPORT_TZ = ZoneInfo("Europe/Helsinki")


def today_helsinki() -> date:
    return datetime.now(SUPPORT_TZ).date()
