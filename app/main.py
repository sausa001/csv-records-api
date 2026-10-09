"""FastAPI app: CSV-backed records API.

Run locally:
    uvicorn app.main:app --reload
Then open http://127.0.0.1:8000/docs
"""
import csv
import io
import logging
import math
import time
from contextlib import asynccontextmanager
from enum import Enum
from typing import Annotated, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Path, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, StreamingResponse

from app.config import Settings, get_settings
from app.models import (
    DepartmentStats,
    ErrorResponse,
    HealthResponse,
    Page,
    Record,
    RecordCreate,
    RecordPatch,
    RecordUpdate,
    StatsResponse,
)
from app.repository import FIELDS, CSVFormatError, DuplicateEmailError, RecordRepository
from app.db_repository import SqlRecordRepository
from app.events import CREATED, DELETED, UPDATED, EventPublisher
from app.metrics import install_metrics

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("csv_records_api")


class SortField(str, Enum):
    id = "id"
    name = "name"
    department = "department"
    city = "city"
    salary = "salary"
    joining_date = "joining_date"


class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


NOT_FOUND = {404: {"model": ErrorResponse, "description": "Record not found"}}
CONFLICT = {409: {"model": ErrorResponse, "description": "Email already in use"}}
UNAUTHORIZED = {401: {"model": ErrorResponse, "description": "Missing or invalid API key"}}


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.sqlalchemy_url:
            app.state.repo = SqlRecordRepository(settings.sqlalchemy_url, seed_csv=settings.seed_csv)
            app.state.storage = app.state.repo.engine.dialect.name
            logger.info("Using %s database: %d records", app.state.storage, app.state.repo.count())
        else:
            app.state.repo = RecordRepository(settings.csv_path)
            app.state.storage = "csv"
            logger.info("Loaded %d records from %s", app.state.repo.count(), settings.csv_path)
        metrics.track_records(app.state.repo.count)
        yield
        if settings.sqlalchemy_url:
            app.state.repo.engine.dispose()

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description="PeoplePulse: a REST API that serves and manages employee records (PostgreSQL, or a CSV file for quick local runs).",
        lifespan=lifespan,
    )
    app.state.settings = settings
    metrics = install_metrics(app)
    # Tests may replace app.state.events with a fake publisher
    app.state.events = EventPublisher(settings.events_topic_arn, settings.aws_region, metrics=metrics)

    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    @app.middleware("http")
    async def timing_and_logging(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"
        logger.info("%s %s -> %d (%.1f ms)", request.method, request.url.path, response.status_code, elapsed_ms)
        return response

    # ---------- dependencies ----------
    def get_repo(request: Request) -> RecordRepository:
        return request.app.state.repo

    def require_api_key(x_api_key: Annotated[Optional[str], Header()] = None) -> None:
        """Protects write endpoints when APP_API_KEY is set."""
        if settings.api_key and x_api_key != settings.api_key:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or invalid API key")

    def get_events(request: Request) -> EventPublisher:
        return request.app.state.events

    Repo = Annotated[RecordRepository, Depends(get_repo)]
    Events = Annotated[EventPublisher, Depends(get_events)]
    RecordId = Annotated[int, Path(ge=1, description="Record id")]
    write_deps = [Depends(require_api_key)]

    def filter_records(
        repo: RecordRepository,
        department: Optional[str],
        city: Optional[str],
        active: Optional[bool],
        min_salary: Optional[int],
        max_salary: Optional[int],
        search: Optional[str],
        sort_by: SortField,
        order: SortOrder,
    ) -> list[Record]:
        if min_salary is not None and max_salary is not None and min_salary > max_salary:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "min_salary cannot be greater than max_salary")
        items = repo.all()
        if department:
            items = [r for r in items if r.department.lower() == department.lower()]
        if city:
            items = [r for r in items if r.city.lower() == city.lower()]
        if active is not None:
            items = [r for r in items if r.active == active]
        if min_salary is not None:
            items = [r for r in items if r.salary >= min_salary]
        if max_salary is not None:
            items = [r for r in items if r.salary <= max_salary]
        if search:
            q = search.lower()
            items = [r for r in items if q in r.name.lower() or q in r.email.lower() or q in r.role.lower()]

        def key(r: Record):
            v = getattr(r, sort_by.value)
            return v.lower() if isinstance(v, str) else v

        return sorted(items, key=key, reverse=order == SortOrder.desc)

    def filters(
        department: Annotated[Optional[str], Query(description="Exact match, case-insensitive")] = None,
        city: Annotated[Optional[str], Query(description="Exact match, case-insensitive")] = None,
        active: Optional[bool] = None,
        min_salary: Annotated[Optional[int], Query(ge=0)] = None,
        max_salary: Annotated[Optional[int], Query(ge=0)] = None,
        search: Annotated[Optional[str], Query(min_length=1, description="Matches name, email or role")] = None,
        sort_by: SortField = SortField.id,
        order: SortOrder = SortOrder.asc,
    ) -> dict:
        return locals()

    Filters = Annotated[dict, Depends(filters)]

    # ---------- general ----------
    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse(url="/docs")

    @app.get("/health", response_model=HealthResponse, tags=["General"])
    def health(repo: Repo, request: Request):
        """Liveness/readiness check: confirms the app is up and its data store answers."""
        return HealthResponse(
            status="ok",
            app=settings.app_name,
            version=settings.version,
            records_loaded=repo.count(),
            csv_file=settings.csv_path.name,
            storage=request.app.state.storage,
        )

    # ---------- read endpoints ----------
    @app.get("/records", response_model=Page[Record], tags=["Records"])
    def list_records(
        repo: Repo,
        f: Filters,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(ge=1)] = 10,
    ):
        """List records with filtering, search, sorting and pagination."""
        page_size = min(page_size, settings.max_page_size)
        items = filter_records(repo, **f)
        total = len(items)
        start = (page - 1) * page_size
        return Page[Record](
            total=total,
            page=page,
            page_size=page_size,
            pages=math.ceil(total / page_size) if total else 0,
            items=items[start : start + page_size],
        )

    @app.get("/records/stats", response_model=StatsResponse, tags=["Records"])
    def record_stats(repo: Repo):
        """Summary numbers: counts, salary range and breakdowns by department and city."""
        items = repo.all()
        if not items:
            return StatsResponse(
                total_records=0, active_records=0, inactive_records=0, avg_salary=0,
                min_salary=0, max_salary=0, by_department=[], by_city={},
            )
        salaries = [r.salary for r in items]
        depts: dict[str, list[int]] = {}
        cities: dict[str, int] = {}
        for r in items:
            depts.setdefault(r.department, []).append(r.salary)
            cities[r.city] = cities.get(r.city, 0) + 1
        active = sum(r.active for r in items)
        return StatsResponse(
            total_records=len(items),
            active_records=active,
            inactive_records=len(items) - active,
            avg_salary=round(sum(salaries) / len(salaries), 2),
            min_salary=min(salaries),
            max_salary=max(salaries),
            by_department=[
                DepartmentStats(department=d, count=len(s), avg_salary=round(sum(s) / len(s), 2))
                for d, s in sorted(depts.items())
            ],
            by_city=dict(sorted(cities.items())),
        )

    @app.get("/records/export", tags=["Records"], response_class=StreamingResponse,
             responses={200: {"content": {"text/csv": {}}, "description": "CSV file"}})
    def export_records(repo: Repo, f: Filters):
        """Download records as CSV. Accepts the same filters as GET /records."""
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        for r in filter_records(repo, **f):
            row = r.model_dump(mode="json")
            row["active"] = str(r.active).lower()
            writer.writerow(row)
        buf.seek(0)
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=records_export.csv"},
        )

    @app.get("/departments", response_model=list[str], tags=["Records"])
    def list_departments(repo: Repo):
        """Distinct department names, sorted."""
        return sorted({r.department for r in repo.all()})

    @app.get("/records/{record_id}", response_model=Record, responses=NOT_FOUND, tags=["Records"])
    def get_record(record_id: RecordId, repo: Repo):
        """Fetch one record by id."""
        rec = repo.get(record_id)
        if rec is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Record {record_id} not found")
        return rec

    # ---------- write endpoints ----------
    @app.post("/records", response_model=Record, status_code=status.HTTP_201_CREATED,
              dependencies=write_deps, responses={**CONFLICT, **UNAUTHORIZED}, tags=["Records"])
    def create_record(data: RecordCreate, repo: Repo, response: Response, events: Events, tasks: BackgroundTasks):
        """Create a record. The id is assigned automatically."""
        try:
            rec = repo.create(data)
        except DuplicateEmailError as e:
            raise HTTPException(status.HTTP_409_CONFLICT, str(e))
        response.headers["Location"] = f"/records/{rec.id}"
        tasks.add_task(events.publish, CREATED, rec.id, rec)
        return rec

    @app.put("/records/{record_id}", response_model=Record, dependencies=write_deps,
             responses={**NOT_FOUND, **CONFLICT, **UNAUTHORIZED}, tags=["Records"])
    def replace_record(record_id: RecordId, data: RecordUpdate, repo: Repo, events: Events, tasks: BackgroundTasks):
        """Replace every field of a record."""
        try:
            rec = repo.replace(record_id, data)
        except DuplicateEmailError as e:
            raise HTTPException(status.HTTP_409_CONFLICT, str(e))
        if rec is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Record {record_id} not found")
        tasks.add_task(events.publish, UPDATED, rec.id, rec)
        return rec

    @app.patch("/records/{record_id}", response_model=Record, dependencies=write_deps,
               responses={**NOT_FOUND, **CONFLICT, **UNAUTHORIZED}, tags=["Records"])
    def update_record(record_id: RecordId, data: RecordPatch, repo: Repo, events: Events, tasks: BackgroundTasks):
        """Update only the fields you send."""
        try:
            rec = repo.patch(record_id, data)
        except DuplicateEmailError as e:
            raise HTTPException(status.HTTP_409_CONFLICT, str(e))
        if rec is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Record {record_id} not found")
        tasks.add_task(events.publish, UPDATED, rec.id, rec)
        return rec

    @app.delete("/records/{record_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=write_deps,
                responses={**NOT_FOUND, **UNAUTHORIZED}, tags=["Records"])
    def delete_record(record_id: RecordId, repo: Repo, events: Events, tasks: BackgroundTasks):
        """Delete a record."""
        if not repo.delete(record_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Record {record_id} not found")
        tasks.add_task(events.publish, DELETED, record_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT, background=tasks)

    # ---------- admin ----------
    @app.post("/admin/reload", dependencies=write_deps, responses=UNAUTHORIZED, tags=["Admin"])
    def reload_csv(repo: Repo):
        """Re-read the CSV from disk (use after editing the file by hand). With a database, returns the row count."""
        try:
            count = repo.load()
        except (CSVFormatError, FileNotFoundError) as e:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Reload failed: {e}")
        return {"status": "reloaded", "records_loaded": count}

    return app


app = create_app()
