"""App settings, read from environment variables (or a .env file)."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")

    app_name: str = "PeoplePulse API"
    version: str = "1.1.0"
    csv_path: Path = BASE_DIR / "data" / "employees.csv"
    # Set APP_API_KEY to protect write endpoints (POST/PUT/PATCH/DELETE/reload).
    # Leave empty to disable auth for local development.
    api_key: str = ""
    max_page_size: int = 100

    # ---- Storage ----------------------------------------------------------
    # Option 1: one URL, e.g. postgresql+psycopg://app:secret@postgres:5432/records
    database_url: str = ""
    # Option 2: separate parts (used in Kubernetes / AWS RDS). The password may contain
    # any characters; it is escaped safely when the URL is built.
    db_host: str = ""
    db_port: int = 5432
    db_name: str = "records"
    db_user: str = "app"
    db_password: str = ""
    # Neither set = use the CSV file at csv_path (handy for quick local runs).

    # ---- Events (Amazon SNS) ---------------------------------------------
    # Topic for record.created / record.updated / record.deleted. Empty = events off.
    events_topic_arn: str = ""
    aws_region: str = ""

    # When the database table is empty on first start, it is filled from this CSV.
    seed_csv: Path = BASE_DIR / "data" / "employees.csv"

    @property
    def sqlalchemy_url(self) -> str:
        """The database URL to use, or "" for CSV storage."""
        if self.database_url:
            return self.database_url
        if self.db_host:
            return URL.create(
                "postgresql+psycopg",
                username=self.db_user,
                password=self.db_password or None,
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
            ).render_as_string(hide_password=False)
        return ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
