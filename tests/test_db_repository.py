"""Unit tests for the SQL data layer (SQLite always; PostgreSQL when TEST_DATABASE_URL is set)."""
import pytest
from sqlalchemy import text

from app.db_repository import SqlRecordRepository
from app.models import RecordCreate, RecordPatch
from app.repository import DuplicateEmailError
from tests.conftest import TEST_DATABASE_URL, reset_database

DB_BACKENDS = ["sqlite"] + (["postgres"] if TEST_DATABASE_URL else [])


@pytest.fixture(params=DB_BACKENDS)
def db_url(request, tmp_path) -> str:
    url = f"sqlite:///{tmp_path / 'unit.db'}" if request.param == "sqlite" else TEST_DATABASE_URL
    reset_database(url)
    return url


def test_seeds_empty_database_from_csv(db_url, csv_file):
    repo = SqlRecordRepository(db_url, seed_csv=csv_file)
    assert repo.count() == 12
    assert repo.get(1).name == "Aarav Sharma"
    assert repo.get(7).active is False


def test_does_not_reseed_existing_data(db_url, csv_file):
    repo = SqlRecordRepository(db_url, seed_csv=csv_file)
    repo.delete(1)
    again = SqlRecordRepository(db_url, seed_csv=csv_file)  # e.g. a pod restart
    assert again.count() == 11
    assert again.get(1) is None


def test_new_ids_continue_after_seeded_ids(db_url, csv_file, new_record):
    repo = SqlRecordRepository(db_url, seed_csv=csv_file)
    assert repo.create(RecordCreate(**new_record)).id == 13


def test_email_unique_case_insensitive(db_url, csv_file, new_record):
    repo = SqlRecordRepository(db_url, seed_csv=csv_file)
    new_record["email"] = "AARAV.SHARMA@example.com"
    with pytest.raises(DuplicateEmailError):
        repo.create(RecordCreate(**new_record))


def test_database_enforces_unique_email_too(db_url, csv_file):
    """Even bypassing the app check, the unique index rejects a duplicate."""
    repo = SqlRecordRepository(db_url, seed_csv=csv_file)
    with pytest.raises(Exception):
        with repo.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO employees (name, email, department, role, city, salary, joining_date, active) "
                "VALUES ('X', 'Priya.Nair@Example.com', 'HR', 'X', 'X', 1, '2024-01-01', true)"
            ))


def test_patch_and_delete(db_url, csv_file):
    repo = SqlRecordRepository(db_url, seed_csv=csv_file)
    assert repo.patch(5, RecordPatch(city="Noida")).city == "Noida"
    assert repo.get(5).city == "Noida"
    assert repo.delete(5) is True
    assert repo.delete(5) is False
    assert repo.patch(5, RecordPatch(city="X")) is None


def test_empty_table_without_seed(db_url):
    repo = SqlRecordRepository(db_url, seed_csv=None)
    assert repo.count() == 0
