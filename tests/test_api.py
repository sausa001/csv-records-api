"""API tests: call the endpoints through FastAPI's TestClient."""
import csv
import io

import pytest

from tests.conftest import API_KEY


# ---------- /health ----------
def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["records_loaded"] == 12
    assert "X-Process-Time-Ms" in r.headers


def test_root_redirects_to_docs(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "/docs"


# ---------- GET /records ----------
def test_list_default_pagination(client):
    body = client.get("/records").json()
    assert body["total"] == 12
    assert body["page"] == 1
    assert body["pages"] == 2
    assert len(body["items"]) == 10
    assert body["items"][0]["id"] == 1


def test_list_second_page(client):
    body = client.get("/records", params={"page": 2, "page_size": 10}).json()
    assert [r["id"] for r in body["items"]] == [11, 12]


def test_page_beyond_end_is_empty(client):
    body = client.get("/records", params={"page": 99}).json()
    assert body["items"] == []
    assert body["total"] == 12


def test_page_size_is_capped(client):
    body = client.get("/records", params={"page_size": 5000}).json()
    assert body["page_size"] == 100


@pytest.mark.parametrize(
    "params, expected_ids",
    [
        ({"department": "engineering"}, [1, 2, 6, 11]),  # case-insensitive
        ({"city": "Delhi"}, [5, 10]),
        ({"active": "false"}, [7, 11]),
        ({"min_salary": 1500000}, [6, 8, 12]),
        ({"max_salary": 950000}, [5, 10]),
        ({"search": "analyst"}, [3, 7]),  # matches role
        ({"department": "Engineering", "active": "true", "city": "Pune"}, [6]),
    ],
)
def test_list_filters(client, params, expected_ids):
    body = client.get("/records", params=params).json()
    assert [r["id"] for r in body["items"]] == expected_ids


def test_sort_by_salary_desc(client):
    items = client.get("/records", params={"sort_by": "salary", "order": "desc", "page_size": 3}).json()["items"]
    assert [r["salary"] for r in items] == [1800000, 1600000, 1550000]


def test_invalid_sort_field(client):
    assert client.get("/records", params={"sort_by": "password"}).status_code == 422


def test_invalid_salary_range(client):
    r = client.get("/records", params={"min_salary": 10, "max_salary": 5})
    assert r.status_code == 400


@pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 0}, {"min_salary": -1}])
def test_invalid_query_params(client, params):
    assert client.get("/records", params=params).status_code == 422


# ---------- GET /records/{id} ----------
def test_get_record(client):
    r = client.get("/records/4")
    assert r.status_code == 200
    assert r.json()["name"] == "Sneha Iyer"


def test_get_missing_record(client):
    r = client.get("/records/999")
    assert r.status_code == 404
    assert r.json()["detail"] == "Record 999 not found"


@pytest.mark.parametrize("bad_id", ["abc", "0", "-1"])
def test_get_invalid_id(client, bad_id):
    assert client.get(f"/records/{bad_id}").status_code == 422


# ---------- stats / departments / export ----------
def test_stats(client):
    body = client.get("/records/stats").json()
    assert body["total_records"] == 12
    assert body["active_records"] == 10
    assert body["inactive_records"] == 2
    assert body["max_salary"] == 1800000
    assert body["min_salary"] == 900000
    eng = next(d for d in body["by_department"] if d["department"] == "Engineering")
    assert eng["count"] == 4
    assert body["by_city"]["Delhi"] == 2


def test_departments(client):
    assert client.get("/departments").json() == ["Data", "Engineering", "Finance", "HR", "Marketing", "Sales"]


def test_export_csv_with_filter(client):
    r = client.get("/records/export", params={"department": "Sales"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert [row["id"] for row in rows] == ["5", "9"]


# ---------- POST /records ----------
def test_create_record(client, new_record):
    r = client.post("/records", json=new_record)
    assert r.status_code == 201
    body = r.json()
    assert body["id"] == 13
    assert r.headers["location"] == "/records/13"
    assert client.get("/records/13").json()["email"] == new_record["email"]
    assert client.get("/health").json()["records_loaded"] == 13


def test_create_persists_to_disk(client, new_record, csv_file):
    client.post("/records", json=new_record)
    assert new_record["email"] in csv_file.read_text()


def test_create_duplicate_email(client, new_record):
    new_record["email"] = "priya.nair@example.com"
    r = client.post("/records", json=new_record)
    assert r.status_code == 409


@pytest.mark.parametrize(
    "field, value",
    [("email", "not-an-email"), ("salary", -5), ("name", ""), ("joining_date", "31-12-2024")],
)
def test_create_validation_errors(client, new_record, field, value):
    new_record[field] = value
    assert client.post("/records", json=new_record).status_code == 422


def test_create_missing_field(client, new_record):
    del new_record["department"]
    assert client.post("/records", json=new_record).status_code == 422


# ---------- PUT / PATCH ----------
def test_replace_record(client, new_record):
    r = client.put("/records/2", json=new_record)
    assert r.status_code == 200
    assert r.json() == {**new_record, "id": 2}


def test_replace_missing_record(client, new_record):
    assert client.put("/records/999", json=new_record).status_code == 404


def test_replace_keeping_own_email_is_allowed(client, new_record):
    new_record["email"] = "priya.nair@example.com"  # record 2's own email
    assert client.put("/records/2", json=new_record).status_code == 200


def test_patch_record(client):
    r = client.patch("/records/5", json={"city": "Noida", "active": False})
    assert r.status_code == 200
    body = r.json()
    assert body["city"] == "Noida"
    assert body["active"] is False
    assert body["name"] == "Vikram Singh"  # untouched


def test_patch_duplicate_email(client):
    r = client.patch("/records/5", json={"email": "aarav.sharma@example.com"})
    assert r.status_code == 409


def test_patch_invalid_value(client):
    assert client.patch("/records/5", json={"salary": -1}).status_code == 422


def test_patch_missing_record(client):
    assert client.patch("/records/999", json={"city": "X"}).status_code == 404


# ---------- DELETE ----------
def test_delete_record(client):
    assert client.delete("/records/3").status_code == 204
    assert client.get("/records/3").status_code == 404
    assert client.delete("/records/3").status_code == 404


def test_new_id_after_delete_does_not_reuse_max(client, new_record):
    client.delete("/records/12")
    client.post("/records", json=new_record)
    ids = [r["id"] for r in client.get("/records", params={"page_size": 100}).json()["items"]]
    assert len(ids) == len(set(ids))


# ---------- admin reload ----------
def test_reload_picks_up_manual_edits(client, csv_file):
    with csv_file.open("a") as f:
        f.write("50,Manual Add,manual@example.com,HR,Recruiter,Delhi,700000,2024-05-01,true\n")
    r = client.post("/admin/reload")
    assert r.status_code == 200
    assert r.json()["records_loaded"] == 13
    assert client.get("/records/50").status_code == 200


def test_reload_bad_csv_keeps_old_data(client, csv_file):
    csv_file.write_text("id,name\n1,Broken\n")
    assert client.post("/admin/reload").status_code == 500
    assert client.get("/health").json()["records_loaded"] == 12


# ---------- API key protection ----------
def test_reads_do_not_need_key(secured_client):
    assert secured_client.get("/records").status_code == 200


def test_write_without_key_rejected(secured_client, new_record):
    assert secured_client.post("/records", json=new_record).status_code == 401
    assert secured_client.delete("/records/1").status_code == 401


def test_write_with_wrong_key_rejected(secured_client, new_record):
    r = secured_client.post("/records", json=new_record, headers={"X-API-Key": "wrong"})
    assert r.status_code == 401


def test_write_with_key_allowed(secured_client, new_record):
    r = secured_client.post("/records", json=new_record, headers={"X-API-Key": API_KEY})
    assert r.status_code == 201


def test_openapi_schema_available(client):
    paths = client.get("/openapi.json").json()["paths"]
    for p in ["/health", "/records", "/records/{record_id}", "/records/stats", "/records/export"]:
        assert p in paths
