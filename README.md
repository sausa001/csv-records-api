# CSV Records API (FastAPI)

A REST API that serves and manages employee records stored in a CSV file, with validation, filtering, pagination, stats, CSV export, optional API-key protection, and a full pytest suite (62 tests, ~98% coverage).

## Project layout

```
csv-records-api/
├── app/
│   ├── main.py         # FastAPI app + all endpoints (create_app factory)
│   ├── models.py       # Pydantic schemas (request/response validation)
│   ├── repository.py   # CSV read/write layer (in-memory + atomic saves)
│   └── config.py       # Settings from env vars / .env
├── data/employees.csv  # Sample data (12 records)
├── tests/
│   ├── conftest.py         # Fixtures: temp CSV copy per test, clients
│   ├── test_api.py         # Endpoint tests
│   └── test_repository.py  # Data-layer unit tests
├── requirements.txt / requirements-dev.txt
└── pytest.ini
```

## Setup and run (macOS / Linux)

```bash
cd csv-records-api
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000/docs** for interactive Swagger docs (you can call every endpoint from the browser), or `/redoc` for reference docs.

## Endpoints

| Method | Path | What it does |
|---|---|---|
| GET | `/health` | App status and number of records loaded |
| GET | `/records` | List with filters, search, sorting, pagination |
| GET | `/records/{id}` | One record (404 if missing) |
| GET | `/records/stats` | Totals, salary min/avg/max, by department and city |
| GET | `/records/export` | Download as CSV (same filters as `/records`) |
| GET | `/departments` | Distinct department names |
| POST | `/records` | Create (id auto-assigned, returns 201 + `Location`) |
| PUT | `/records/{id}` | Replace all fields |
| PATCH | `/records/{id}` | Update only the fields sent |
| DELETE | `/records/{id}` | Delete (204) |
| POST | `/admin/reload` | Re-read the CSV after editing it by hand |

**Query parameters for `/records` and `/records/export`:**
`department`, `city` (case-insensitive exact match), `active` (true/false), `min_salary`, `max_salary`, `search` (in name, email, role), `sort_by` (id, name, department, city, salary, joining_date), `order` (asc/desc), `page`, `page_size` (max 100; `/records` only).

## Try it with curl

```bash
curl http://127.0.0.1:8000/health
curl "http://127.0.0.1:8000/records?department=Engineering&sort_by=salary&order=desc"
curl http://127.0.0.1:8000/records/3
curl http://127.0.0.1:8000/records/stats

curl -X POST http://127.0.0.1:8000/records -H "Content-Type: application/json" -d '{
  "name": "New Person", "email": "new@example.com", "department": "HR",
  "role": "Recruiter", "city": "Delhi", "salary": 800000, "joining_date": "2025-06-01"
}'

curl -X PATCH http://127.0.0.1:8000/records/13 -H "Content-Type: application/json" -d '{"city": "Noida"}'
curl -X DELETE http://127.0.0.1:8000/records/13
curl -o export.csv "http://127.0.0.1:8000/records/export?city=Pune"
```

## Run the tests

```bash
pytest                                   # all 62 tests
pytest -v                                # show each test name
pytest --cov=app --cov-report=term-missing   # with coverage
pytest tests/test_api.py -k patch        # just the PATCH tests
```

Each test works on its own temporary copy of the CSV, so running the tests never changes `data/employees.csv`.

## Configuration

Set these as environment variables or in a `.env` file (see `.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `APP_CSV_PATH` | `data/employees.csv` | Which CSV file to serve |
| `APP_API_KEY` | *(empty = off)* | If set, write endpoints require header `X-API-Key: <value>` |
| `APP_MAX_PAGE_SIZE` | `100` | Upper limit for `page_size` |

```bash
APP_API_KEY=mysecret uvicorn app.main:app --reload
curl -X DELETE http://127.0.0.1:8000/records/1 -H "X-API-Key: mysecret"
```

## Design notes

- **Validation:** Pydantic checks every field (valid email, salary ≥ 0, ISO dates, non-empty strings). Bad input returns 422 with details. Bad CSV rows fail at startup with the line number.
- **Error codes:** 400 for an invalid salary range, 401 for a bad API key, 404 for a missing record, 409 for a duplicate email, 422 for validation errors.
- **Safe writes:** changes are written to a temp file and then swapped in atomically, so a crash can't leave a half-written CSV. A lock guards concurrent requests.
- **Testable:** `create_app(settings)` lets the tests point the app at a temp CSV.
- **Every response** carries an `X-Process-Time-Ms` header, and each request is logged.
- **Limits:** a CSV file suits small datasets and a single server process. For more data or several workers, replace `RecordRepository` with a database (SQLite/Postgres); the endpoints wouldn't need to change.
