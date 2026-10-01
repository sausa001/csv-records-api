"""Data layer: loads records from the CSV file and writes changes back to it.

All data lives in memory for fast reads. Every change is written back to the
CSV through a temp file + atomic rename, so a crash mid-write can't corrupt it.
A lock keeps concurrent requests from stepping on each other.
"""
import csv
import os
import tempfile
import threading
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from app.models import Record, RecordCreate, RecordPatch, RecordUpdate

# Column order in the CSV: id first, then the record fields.
FIELDS = ["id", *(f for f in Record.model_fields if f != "id")]


class CSVFormatError(Exception):
    """Raised when the CSV is missing columns or has bad rows."""


class DuplicateEmailError(Exception):
    """Raised when a create/update would reuse another record's email."""


class RecordRepository:
    def __init__(self, csv_path: Path):
        self.csv_path = Path(csv_path)
        self._lock = threading.RLock()
        self._records: dict[int, Record] = {}
        self.load()

    # ---------- loading / saving ----------
    def load(self) -> int:
        """(Re)load all rows from the CSV. Returns the number of records."""
        if not self.csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {self.csv_path}")

        records: dict[int, Record] = {}
        with self.csv_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            missing = set(FIELDS) - set(reader.fieldnames or [])
            if missing:
                raise CSVFormatError(f"CSV is missing columns: {sorted(missing)}")
            for line_no, row in enumerate(reader, start=2):  # line 1 is the header
                try:
                    rec = Record.model_validate(
                        {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k in FIELDS}
                    )
                except ValidationError as e:
                    raise CSVFormatError(f"Invalid row on line {line_no}: {e.errors()[0]['msg']}") from e
                if rec.id in records:
                    raise CSVFormatError(f"Duplicate id {rec.id} on line {line_no}")
                records[rec.id] = rec

        with self._lock:
            self._records = records
        return len(records)

    def _save(self) -> None:
        """Write all records to a temp file, then atomically replace the CSV."""
        fd, tmp = tempfile.mkstemp(dir=self.csv_path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
                writer.writeheader()
                for rec in sorted(self._records.values(), key=lambda r: r.id):
                    row = rec.model_dump(mode="json")
                    row["active"] = str(rec.active).lower()
                    writer.writerow(row)
            os.replace(tmp, self.csv_path)
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

    # ---------- reads ----------
    def count(self) -> int:
        return len(self._records)

    def all(self) -> list[Record]:
        with self._lock:
            return sorted(self._records.values(), key=lambda r: r.id)

    def get(self, record_id: int) -> Optional[Record]:
        return self._records.get(record_id)

    # ---------- writes ----------
    def _check_email(self, email: str, exclude_id: Optional[int] = None) -> None:
        for r in self._records.values():
            if r.email.lower() == email.lower() and r.id != exclude_id:
                raise DuplicateEmailError(f"Email already in use by record {r.id}")

    def create(self, data: RecordCreate) -> Record:
        with self._lock:
            self._check_email(data.email)
            new_id = max(self._records, default=0) + 1
            rec = Record(id=new_id, **data.model_dump())
            self._records[new_id] = rec
            self._save()
            return rec

    def replace(self, record_id: int, data: RecordUpdate) -> Optional[Record]:
        with self._lock:
            if record_id not in self._records:
                return None
            self._check_email(data.email, exclude_id=record_id)
            rec = Record(id=record_id, **data.model_dump())
            self._records[record_id] = rec
            self._save()
            return rec

    def patch(self, record_id: int, data: RecordPatch) -> Optional[Record]:
        with self._lock:
            current = self._records.get(record_id)
            if current is None:
                return None
            changes = data.model_dump(exclude_unset=True, exclude_none=True)
            if "email" in changes:
                self._check_email(changes["email"], exclude_id=record_id)
            rec = current.model_copy(update=changes)
            Record.model_validate(rec.model_dump())  # re-validate merged record
            self._records[record_id] = rec
            self._save()
            return rec

    def delete(self, record_id: int) -> bool:
        with self._lock:
            if self._records.pop(record_id, None) is None:
                return False
            self._save()
            return True
