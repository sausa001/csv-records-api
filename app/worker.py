"""Event worker: reads employee events from Amazon SQS and processes them.

Run:  python -m app.worker
Env:  APP_EVENTS_QUEUE_URL  the SQS queue subscribed to the SNS topic (required)
      AWS_REGION            e.g. us-west-1
      APP_WORKER_METRICS_PORT  Prometheus metrics port (default 9101)

Processing here is an audit log line per event; this is the place to add real work
(sync to an HR system, send a welcome message, ...). A message that fails 5 times
moves to the dead-letter queue, where a CloudWatch alarm notices it.
"""
import json
import logging
import os
import signal
import sys
from typing import Any

from prometheus_client import CollectorRegistry, Counter, start_http_server

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("peoplepulse.worker")


def parse_event(body: str) -> dict:
    """Accepts both raw SNS delivery (the event itself) and the SNS envelope."""
    data = json.loads(body)
    if isinstance(data, dict) and data.get("Type") == "Notification" and "Message" in data:
        data = json.loads(data["Message"])
    if not isinstance(data, dict) or "event" not in data:
        raise ValueError("not a PeoplePulse event")
    return data


class Worker:
    def __init__(self, queue_url: str, client: Any, registry: CollectorRegistry):
        self.queue_url = queue_url
        self.client = client
        self.running = True
        self.processed = Counter(
            "peoplepulse_events_processed_total", "Events read from SQS",
            ["event", "result"], registry=registry,
        )

    def handle(self, event: dict) -> None:
        logger.info("AUDIT %s record=%s name=%s department=%s at=%s",
                    event["event"], event.get("record_id"), event.get("name", "-"),
                    event.get("department", "-"), event.get("at"))

    def poll_once(self) -> int:
        resp = self.client.receive_message(
            QueueUrl=self.queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=20,
            MessageAttributeNames=["All"],
        )
        messages = resp.get("Messages", [])
        for m in messages:
            try:
                event = parse_event(m["Body"])
                self.handle(event)
            except Exception:
                # leave it on the queue: SQS retries it, then moves it to the dead-letter queue
                self.processed.labels("unknown", "error").inc()
                logger.exception("Failed to process message %s", m.get("MessageId"))
                continue
            self.client.delete_message(QueueUrl=self.queue_url, ReceiptHandle=m["ReceiptHandle"])
            self.processed.labels(event["event"], "ok").inc()
        return len(messages)

    def run(self) -> None:
        logger.info("Worker started, queue %s", self.queue_url)
        while self.running:
            try:
                self.poll_once()
            except Exception:
                logger.exception("Polling failed; retrying")
        logger.info("Worker stopped")

    def stop(self, *_: Any) -> None:
        self.running = False


def main() -> None:
    queue_url = os.environ.get("APP_EVENTS_QUEUE_URL", "")
    if not queue_url:
        logger.error("APP_EVENTS_QUEUE_URL is not set")
        sys.exit(1)
    import boto3

    registry = CollectorRegistry()
    start_http_server(int(os.environ.get("APP_WORKER_METRICS_PORT", "9101")), registry=registry)
    worker = Worker(queue_url, boto3.client("sqs"), registry)
    signal.signal(signal.SIGTERM, worker.stop)
    signal.signal(signal.SIGINT, worker.stop)
    worker.run()


if __name__ == "__main__":
    main()
