"""Unit tests for the CSV data layer (no HTTP involved)."""
import pytest

from app.models import RecordCreate, RecordPatch
from app.repository import CSVFormatError, DuplicateEmailError, RecordRepository


def test_loads_all_rows(csv_file):
    repo = RecordRepository(csv_file)
    assert repo.count() == 12
    assert repo.get(1).name == "Aarav Sharma"


def test_parses_types(csv_file):
    rec = RecordRepository(csv_file).get(7)
    assert isinstance(rec.salary, int)
    assert rec.active is False
    assert rec.joining_date.year == 2021


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        RecordRepository(tmp_path / "nope.csv")


def test_missing_column_raises(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("id,name\n1,Someone\n")
    with pytest.raises(CSVFormatError, match="missing columns"):
        RecordRepository(bad)


def test_bad_row_reports_line_number(csv_file):
    with csv_file.open("a") as f:
        f.write("13,Bad Row,bad@example.com,HR,Intern,Delhi,not-a-number,2024-01-01,true\n")
    with pytest.raises(CSVFormatError, match="line 14"):
        RecordRepository(csv_file)


def test_duplicate_id_raises(csv_file):
    with csv_file.open("a") as f:
        f.write("1,Dup,dup@example.com,HR,Intern,Delhi,100,2024-01-01,true\n")
    with pytest.raises(CSVFormatError, match="Duplicate id 1"):
        RecordRepository(csv_file)


def test_create_persists_to_csv(csv_file, new_record):
    repo = RecordRepository(csv_file)
    rec = repo.create(RecordCreate(**new_record))
    assert rec.id == 13
    reloaded = RecordRepository(csv_file)  # fresh read from disk
    assert reloaded.get(13).email == new_record["email"]


def test_create_duplicate_email_rejected(csv_file, new_record):
    repo = RecordRepository(csv_file)
    new_record["email"] = "AARAV.SHARMA@example.com"  # case-insensitive match
    with pytest.raises(DuplicateEmailError):
        repo.create(RecordCreate(**new_record))


def test_patch_changes_only_given_fields(csv_file):
    repo = RecordRepository(csv_file)
    before = repo.get(2)
    after = repo.patch(2, RecordPatch(salary=1300000))
    assert after.salary == 1300000
    assert after.name == before.name


def test_delete_persists(csv_file):
    repo = RecordRepository(csv_file)
    assert repo.delete(3) is True
    assert repo.delete(3) is False
    assert RecordRepository(csv_file).get(3) is None


def test_no_temp_files_left_behind(csv_file, new_record):
    RecordRepository(csv_file).create(RecordCreate(**new_record))
    assert list(csv_file.parent.glob("*.tmp")) == []
