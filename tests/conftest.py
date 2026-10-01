"""Shared fixtures. Every test gets its own copy of the CSV, so writes never touch the real data."""
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

SAMPLE_CSV = Path(__file__).resolve().parent.parent / "data" / "employees.csv"
API_KEY = "test-secret"

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


@pytest.fixture
def csv_file(tmp_path) -> Path:
    dest = tmp_path / "employees.csv"
    shutil.copy(SAMPLE_CSV, dest)
    return dest


@pytest.fixture
def client(csv_file):
    app = create_app(Settings(csv_path=csv_file, api_key=""))
    with TestClient(app) as c:  # "with" runs the startup (lifespan) code
        yield c


@pytest.fixture
def secured_client(csv_file):
    app = create_app(Settings(csv_path=csv_file, api_key=API_KEY))
    with TestClient(app) as c:
        yield c


@pytest.fixture
def new_record() -> dict:
    return dict(NEW_RECORD)
