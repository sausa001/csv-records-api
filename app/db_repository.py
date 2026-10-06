"""PostgreSQL data layer (SQLAlchemy 2.0).

Same public interface as the CSV `RecordRepository`, so the API code does not
care which one it gets. Works with PostgreSQL in Kubernetes / AWS RDS, and with
SQLite in unit tests.

On first start against an empty database the table is created and filled from
the seed CSV (data/employees.csv), so a fresh environment comes up with data.
"""
import logging
import time
from datetime import date
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    Index,
    Integer,
    String,
    create_engine,
    func,
    insert,
    select,
    text,
)
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from app.models import Record, RecordCreate, RecordPatch, RecordUpdate
from app.repository import DuplicateEmailError, RecordRepository

logger = logging.getLogger("csv_records_api.db")

SEED_LOCK_ID = 424242  # Postgres advisory lock: only one replica seeds an empty database


class Base(DeclarativeBase):
    pass


class EmployeeRow(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(254))
    department: Mapped[str] = mapped_column(String(50), index=True)
    role: Mapped[str] = mapped_column(String(80))
    city: Mapped[str] = mapped_column(String(50), index=True)
    salary: Mapped[int] = mapped_column(BigInteger)
    joining_date: Mapped[date] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        # Case-insensitive unique email, enforced by the database itself
        Index("uq_employees_email_lower", func.lower(email), unique=True),
    )


def _to_record(row: EmployeeRow) -> Record:
    return Record.model_validate(row)


class SqlRecordRepository:
    """Records stored in a SQL database (PostgreSQL in production)."""

    def __init__(self, database_url: str, seed_csv: Optional[Path] = None,
                 connect_retries: int = 30, retry_delay: float = 2.0):
        self.engine = create_engine(database_url, pool_pre_ping=True)
        self._wait_for_database(connect_retries, retry_delay)
        self._create_schema_and_seed(Path(seed_csv) if seed_csv else None)

    # ---------- startup ----------
    def _wait_for_database(self, retries: int, delay: float) -> None:
        """Kubernetes may start the API before Postgres is ready: retry for a while."""
        for attempt in range(1, retries + 1):
            try:
                with self.engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                return
            except OperationalError:
                if attempt == retries:
                    raise
                logger.warning("Database not ready (attempt %d/%d), retrying in %.0fs", attempt, retries, delay)
                time.sleep(delay)

    def _create_schema_and_seed(self, csv_path: Optional[Path]) -> None:
        """Create the table and, if it is empty, fill it from the seed CSV.

        Runs in ONE transaction holding a Postgres advisory lock, so when several
        replicas start together on an empty database only one creates and seeds it;
        the others wait, then see the finished table.
        """
        with self.engine.begin() as conn:
            if self.engine.dialect.name == "postgresql":
                conn.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": SEED_LOCK_ID})
            Base.metadata.create_all(conn)
            if csv_path is None:
                return
            if conn.scalar(select(func.count()).select_from(EmployeeRow)):
                return
            if not csv_path.exists():
                logger.warning("Seed CSV %s not found; starting with an empty table", csv_path)
                return
            records = RecordRepository(csv_path).all()  # reuses the CSV validation
            if records:
                conn.execute(insert(EmployeeRow), [r.model_dump() for r in records])
            if self.engine.dialect.name == "postgresql":
                # explicit ids were inserted: move the id sequence past them
                conn.execute(text(
                    "SELECT setval(pg_get_serial_sequence('employees', 'id'), "
                    "COALESCE((SELECT MAX(id) FROM employees), 0) + 1, false)"
                ))
            logger.info("Seeded %d records from %s", len(records), csv_path)

    # ---------- interface shared with the CSV repository ----------
    def load(self) -> int:
        """Nothing to re-read for a database; returns the current row count."""
        return self.count()

    def count(self) -> int:
        with Session(self.engine) as s:
            return s.scalar(select(func.count()).select_from(EmployeeRow)) or 0

    def all(self) -> list[Record]:
        with Session(self.engine) as s:
            return [_to_record(r) for r in s.scalars(select(EmployeeRow).order_by(EmployeeRow.id))]

    def get(self, record_id: int) -> Optional[Record]:
        with Session(self.engine) as s:
            row = s.get(EmployeeRow, record_id)
            return _to_record(row) if row else None

    def _check_email(self, s: Session, email: str, exclude_id: Optional[int] = None) -> None:
        q = select(EmployeeRow.id).where(func.lower(EmployeeRow.email) == email.lower())
        if exclude_id is not None:
            q = q.where(EmployeeRow.id != exclude_id)
        other = s.scalar(q)
        if other is not None:
            raise DuplicateEmailError(f"Email already in use by record {other}")

    def create(self, data: RecordCreate) -> Record:
        try:
            with Session(self.engine) as s, s.begin():
                self._check_email(s, data.email)
                row = EmployeeRow(**data.model_dump())
                s.add(row)
                s.flush()
                return _to_record(row)
        except IntegrityError as e:  # two requests raced with the same email
            raise DuplicateEmailError("Email already in use") from e

    def replace(self, record_id: int, data: RecordUpdate) -> Optional[Record]:
        try:
            with Session(self.engine) as s, s.begin():
                row = s.get(EmployeeRow, record_id)
                if row is None:
                    return None
                self._check_email(s, data.email, exclude_id=record_id)
                for k, v in data.model_dump().items():
                    setattr(row, k, v)
                s.flush()
                return _to_record(row)
        except IntegrityError as e:
            raise DuplicateEmailError("Email already in use") from e

    def patch(self, record_id: int, data: RecordPatch) -> Optional[Record]:
        try:
            with Session(self.engine) as s, s.begin():
                row = s.get(EmployeeRow, record_id)
                if row is None:
                    return None
                changes = data.model_dump(exclude_unset=True, exclude_none=True)
                if "email" in changes:
                    self._check_email(s, changes["email"], exclude_id=record_id)
                merged = _to_record(row).model_copy(update=changes)
                Record.model_validate(merged.model_dump())  # re-validate merged record
                for k, v in changes.items():
                    setattr(row, k, v)
                s.flush()
                return _to_record(row)
        except IntegrityError as e:
            raise DuplicateEmailError("Email already in use") from e

    def delete(self, record_id: int) -> bool:
        with Session(self.engine) as s, s.begin():
            row = s.get(EmployeeRow, record_id)
            if row is None:
                return False
            s.delete(row)
            return True
