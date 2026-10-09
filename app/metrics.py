"""Prometheus metrics for the API, exposed on GET /metrics.

Each app instance gets its own registry, so creating several apps (as the tests do)
never registers the same metric twice. Prometheus scrapes the pods directly inside the
cluster; nginx does not forward /api/metrics, so the metrics are not public.
"""
import time
from typing import Callable, Optional

from fastapi import FastAPI, Request
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram, generate_latest

SKIP_PATHS = {"/metrics"}


class ApiMetrics:
    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        self.requests = Counter(
            "peoplepulse_http_requests_total", "HTTP requests handled",
            ["method", "route", "status"], registry=self.registry,
        )
        self.latency = Histogram(
            "peoplepulse_http_request_duration_seconds", "Time to handle an HTTP request",
            ["method", "route"], registry=self.registry,
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
        )
        self.events = Counter(
            "peoplepulse_events_published_total", "Domain events sent to Amazon SNS",
            ["event", "result"], registry=self.registry,
        )
        self.records = Gauge("peoplepulse_records", "Employee records currently stored", registry=self.registry)

    def track_records(self, count: Callable[[], int]) -> None:
        """The record count is read when Prometheus scrapes, not on every request."""
        def safe_count() -> float:
            try:
                return float(count())
            except Exception:  # database briefly unavailable: report nothing useful rather than fail the scrape
                return float("nan")
        self.records.set_function(safe_count)


def install_metrics(app: FastAPI) -> ApiMetrics:
    metrics = ApiMetrics()
    app.state.metrics = metrics

    @app.middleware("http")
    async def prometheus_middleware(request: Request, call_next):
        if request.url.path in SKIP_PATHS:
            return await call_next(request)
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            route = _route_template(request)
            metrics.requests.labels(request.method, route, str(status_code)).inc()
            metrics.latency.labels(request.method, route).observe(time.perf_counter() - start)

    @app.get("/metrics", include_in_schema=False)
    def prometheus_metrics() -> Response:
        return Response(generate_latest(metrics.registry), media_type=CONTENT_TYPE_LATEST)

    return metrics


def _route_template(request: Request) -> str:
    """'/records/{record_id}' rather than '/records/17', so label values stay few."""
    route = request.scope.get("route")
    path: Optional[str] = getattr(route, "path", None)
    return path or "unmatched"
