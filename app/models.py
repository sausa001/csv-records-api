"""Pydantic schemas: what the API accepts and returns."""
from datetime import date
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field

T = TypeVar("T")


class RecordBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, examples=["Saket Saurabh"])
    email: EmailStr = Field(..., examples=["saket.saurabh@example.com"])
    department: str = Field(..., min_length=1, max_length=50, examples=["Engineering"])
    role: str = Field(..., min_length=1, max_length=80, examples=["Lead DevOps Architect"])
    city: str = Field(..., min_length=1, max_length=50, examples=["Bengaluru"])
    salary: int = Field(..., ge=0, examples=[8450000])
    joining_date: date = Field(..., examples=["2021-08-01"])
    active: bool = True


class RecordCreate(RecordBase):
    """Body for POST /records (id is assigned by the server)."""


class RecordUpdate(RecordBase):
    """Body for PUT /records/{id} (full replace)."""


class RecordPatch(BaseModel):
    """Body for PATCH /records/{id}; every field is optional."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    department: Optional[str] = Field(None, min_length=1, max_length=50)
    role: Optional[str] = Field(None, min_length=1, max_length=80)
    city: Optional[str] = Field(None, min_length=1, max_length=50)
    salary: Optional[int] = Field(None, ge=0)
    joining_date: Optional[date] = None
    active: Optional[bool] = None


class _WithId(BaseModel):
    id: int = Field(..., ge=1, examples=[1])


class Record(RecordBase, _WithId):
    """A stored record. `id` comes first in the JSON output."""

    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    total: int
    page: int
    page_size: int
    pages: int
    items: list[T]


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    records_loaded: int
    csv_file: str
    storage: str = "csv"  # "csv" or the database type, e.g. "postgresql"


class DepartmentStats(BaseModel):
    department: str
    count: int
    avg_salary: float


class StatsResponse(BaseModel):
    total_records: int
    active_records: int
    inactive_records: int
    avg_salary: float
    min_salary: int
    max_salary: int
    by_department: list[DepartmentStats]
    by_city: dict[str, int]


class ErrorResponse(BaseModel):
    detail: str
