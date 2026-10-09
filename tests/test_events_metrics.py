"""Prometheus /metrics, SNS event publishing and the SQS worker."""
import json

import pytest
from prometheus_client import CollectorRegistry

from app.events import CREATED, DELETED, UPDATED, EventPublisher
from app.worker import Worker, parse_event
from tests.conftest import NEW_RECORD


class FakeSNS:
    def __init__(self, fail: bool = False):
        self.calls = []
        self.fail = fail

    def publish(self, **kwargs):
        if self.fail:
            raise RuntimeError("SNS unavailable")
        self.calls.append(kwargs)
        return {"MessageId": "1"}


@pytest.fixture
def sns(client):
    fake = FakeSNS()
    app = client.app
    app.state.events = EventPublisher("arn:aws:sns:us-west-1:123456789012:test", "us-west-1",
                                      client=fake, metrics=app.state.metrics)
    return fake


def sent(fake):
    return [(c["MessageAttributes"]["event"]["StringValue"], json.loads(c["Message"])) for c in fake.calls]


# ---------- metrics ----------
def test_metrics_endpoint(client):
    client.get("/records")
    client.get("/records/1")
    body = client.get("/metrics").text
    assert "peoplepulse_http_requests_total" in body
    assert 'route="/records/{record_id}"' in body          # templated, not /records/1
    assert 'route="/records"' in body
    assert "peoplepulse_records " in body


def test_metrics_not_in_openapi(client):
    assert "/metrics" not in client.get("/openapi.json").json()["paths"]


def test_two_apps_do_not_clash(settings_for):
    from app.main import create_app
    create_app(settings_for())
    create_app(settings_for())        # would raise "Duplicated timeseries" with a shared registry


# ---------- publishing ----------
def test_events_off_by_default(client):
    assert client.app.state.events.enabled is False
    assert client.post("/records", json=NEW_RECORD).status_code == 201


def test_create_update_delete_publish_events(client, sns):
    rec = client.post("/records", json=NEW_RECORD).json()
    client.patch(f"/records/{rec['id']}", json={"city": "Delhi"})
    client.put(f"/records/{rec['id']}", json={**NEW_RECORD, "role": "Lead SRE"})
    client.delete(f"/records/{rec['id']}")
    events = sent(sns)
    assert [e for e, _ in events] == [CREATED, UPDATED, UPDATED, DELETED]
    created = events[0][1]
    assert created["record_id"] == rec["id"] and created["name"] == "Test User"
    assert "salary" not in created and "email" not in created     # no personal data in events


def test_failed_requests_publish_nothing(client, sns):
    client.post("/records", json={**NEW_RECORD, "email": "bad"})
    client.delete("/records/99999")
    assert sns.calls == []


def test_publish_failure_does_not_break_api(client):
    app = client.app
    app.state.events = EventPublisher("arn:x", client=FakeSNS(fail=True), metrics=app.state.metrics)
    assert client.post("/records", json=NEW_RECORD).status_code == 201
    assert 'peoplepulse_events_published_total{event="record.created",result="error"} 1.0' in client.get("/metrics").text


# ---------- worker ----------
def test_parse_raw_and_enveloped_messages():
    event = {"event": CREATED, "record_id": 7}
    assert parse_event(json.dumps(event)) == event
    assert parse_event(json.dumps({"Type": "Notification", "Message": json.dumps(event)})) == event
    with pytest.raises(ValueError):
        parse_event(json.dumps({"hello": "world"}))


class FakeSQS:
    def __init__(self, bodies):
        self.messages = [{"MessageId": str(i), "ReceiptHandle": f"r{i}", "Body": b} for i, b in enumerate(bodies)]
        self.deleted = []

    def receive_message(self, **_):
        return {"Messages": self.messages}

    def delete_message(self, QueueUrl, ReceiptHandle):
        self.deleted.append(ReceiptHandle)


def test_worker_deletes_good_messages_and_keeps_bad_ones():
    sqs = FakeSQS([json.dumps({"event": CREATED, "record_id": 1}), "not json"])
    worker = Worker("https://sqs/queue", sqs, CollectorRegistry())
    assert worker.poll_once() == 2
    assert sqs.deleted == ["r0"]          # the bad one stays for retry, then the dead-letter queue
