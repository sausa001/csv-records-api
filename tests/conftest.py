"""Shared fixtures.

Every test gets its own copy of the CSV, so writes never touch the real data.
API tests run once per storage backend:
  - csv:      the CSV file repository
  - sqlite:   the SQL repository on a throwaway SQLite file (no server needed)
  - postgres: the SQL repository on a real PostgreSQL, only when TEST_DATABASE_URL is set,
              e.g. TEST_DATABASE_URL=postgresql+psycopg://app:apppass@localhost:5432/records_test
"""
import os
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.config import Settings
from app.db_repository import Base
from app.main import create_app

# Fixed test data, separate from the real data/employees.csv so editing the real
# data never breaks the tests.
SAMPLE_CSV = Path(__file__).resolve().parent / "data" / "employees.csv"
API_KEY = "test-secret"
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")

BACKENDS = ["csv", "sqlite"] + (["postgres"] if TEST_DATABASE_URL else [])

NEW_RECORD = {
    "name": "Test User",
    "email": "test.user@example.com",
    "department": "Engineering",
    "role": "SRE",
    "city": "Pune",
    "salary": 1200000,
    "joining_date": "2024-01-15",
    "active": True,
}


def reset_database(url: str) -> None:
    """Drop the table so each test starts from the seed data."""
    engine = create_engine(url)
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def csv_file(tmp_path) -> Path:
    dest = tmp_path / "employees.csv"
    shutil.copy(SAMPLE_CSV, dest)
    return dest


@pytest.fixture(params=BACKENDS)
def backend(request) -> str:
    if request.param != "csv" and request.node.get_closest_marker("csv_only"):
        pytest.skip("CSV-specific behaviour")
    return request.param


@pytest.fixture
def settings_for(backend, csv_file, tmp_path):
    def make(api_key: str = "") -> Settings:
        if backend == "csv":
            return Settings(csv_path=csv_file, api_key=api_key, database_url="")
        url = f"sqlite:///{tmp_path / 'test.db'}" if backend == "sqlite" else TEST_DATABASE_URL
        reset_database(url)
        return Settings(csv_path=csv_file, api_key=api_key, database_url=url, seed_csv=csv_file)
    return make


@pytest.fixture
def client(settings_for):
    app = create_app(settings_for())
    with TestClient(app) as c:  # "with" runs the startup (lifespan) code
        yield c


@pytest.fixture
def secured_client(settings_for):
    app = create_app(settings_for(API_KEY))
    with TestClient(app) as c:
        yield c


@pytest.fixture
def new_record() -> dict:
    return dict(NEW_RECORD)
