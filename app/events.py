"""Domain events: every change to an employee record is announced on Amazon SNS.

    API --publish--> SNS topic --> SQS queue (+ dead-letter queue) --> worker (app/worker.py)
                               \-> optional e-mail subscription for new employees

Publishing is switched off when APP_EVENTS_TOPIC_ARN is empty (local runs, Minikube,
tests), and a failure to publish never fails the API request: it is logged and counted.
Messages carry no salary or e-mail address, only what a downstream system needs.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("csv_records_api.events")

CREATED, UPDATED, DELETED = "record.created", "record.updated", "record.deleted"


class EventPublisher:
    def __init__(self, topic_arn: str = "", region: str = "", client: Any = None, metrics: Any = None):
        self.topic_arn = topic_arn
        self.region = region or None
        self._client = client
        self.metrics = metrics

    @property
    def enabled(self) -> bool:
        return bool(self.topic_arn)

    @property
    def client(self):
        if self._client is None:
            import boto3  # imported lazily: not needed when events are off
            self._client = boto3.client("sns", region_name=self.region)
        return self._client

    @staticmethod
    def build_message(event: str, record_id: int, record: Optional[Any] = None) -> dict:
        msg = {"event": event, "record_id": record_id, "at": datetime.now(timezone.utc).isoformat()}
        if record is not None:
            msg.update(name=record.name, department=record.department, city=record.city, active=record.active)
        return msg

    def publish(self, event: str, record_id: int, record: Optional[Any] = None) -> bool:
        if not self.enabled:
            return False
        message = self.build_message(event, record_id, record)
        try:
            self.client.publish(
                TopicArn=self.topic_arn,
                Message=json.dumps(message),
                MessageAttributes={"event": {"DataType": "String", "StringValue": event}},
            )
            self._count(event, "ok")
            logger.info("Published %s for record %s", event, record_id)
            return True
        except Exception:
            self._count(event, "error")
            logger.exception("Could not publish %s for record %s", event, record_id)
            return False

    def _count(self, event: str, result: str) -> None:
        if self.metrics is not None:
            self.metrics.events.labels(event, result).inc()
