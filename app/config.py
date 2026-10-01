"""App settings, read from environment variables (or a .env file)."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")

    app_name: str = "CSV Records API"
    version: str = "1.0.0"
    csv_path: Path = BASE_DIR / "data" / "employees.csv"
    # Set APP_API_KEY to protect write endpoints (POST/PUT/PATCH/DELETE/reload).
    # Leave empty to disable auth for local development.
    api_key: str = ""
    max_page_size: int = 100


@lru_cache
def get_settings() -> Settings:
    return Settings()

    


