"""FastAPI app.

Run:  uvicorn api.app:app --reload        (from the HourlyDetectionEngine folder)
Docs: http://127.0.0.1:8000/docs

Env vars: DETECTION_DB, DETECTION_RULES, DETECTION_API_KEY, ALERT_WEBHOOK_URL, AUTO_SCHEDULE=1
"""
from __future__ import annotations

import os
import secrets
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, Response, Security, status
from fastapi.security import APIKeyHeader

from api.schemas import EventBatch, RuleIn, RunRequest
from service.container import Container, build_container
from service.models import Event, HourWindow, utcnow
from service.rules import RuleConfigError

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(key: str | None = Security(_api_key_header)) -> None:
    expected = os.getenv("DETECTION_API_KEY")
    if expected and not (key and secrets.compare_digest(key, expected)):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or missing API key")


def get_container(request: Request) -> Container:
    return request.app.state.container


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    container = build_container(
        db_path=os.getenv("DETECTION_DB", "detections.db"),
        rules_path=os.getenv("DETECTION_RULES") or None,
        webhook_url=os.getenv("ALERT_WEBHOOK_URL") or None,
    )
    app.state.container = container
    if os.getenv("AUTO_SCHEDULE") == "1":
        container.scheduler.start()
        container.watchdog.start()
    try:
        yield
    finally:
        container.scheduler.stop()
        container.watchdog.stop()


app = FastAPI(title="Hourly Detection Engine", version="1.0.0", lifespan=lifespan)
public = APIRouter(tags=["health"])
api = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])


def _hour(ts: datetime | None) -> datetime | None:
    if ts is None:
        return None
    ts = ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts
    return HourWindow.of(ts).start


# ------------------------------------------------------------------ health

@public.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@public.get("/health/detections")
def detections_health(response: Response, c: Container = Depends(get_container)) -> dict[str, Any]:
    """For an external monitor (dead-man's switch): 503 when no run succeeded in the last 2 hours."""
    last = c.store.last_successful_run()
    healthy = last is not None and utcnow() - last < timedelta(hours=2)
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if healthy else "stale", "last_successful_run": last}


# ------------------------------------------------------------------ events

@api.post("/events", status_code=status.HTTP_202_ACCEPTED, tags=["events"])
def ingest(batch: EventBatch, c: Container = Depends(get_container)) -> dict[str, int]:
    events = [Event(e.event_id, e.source, e.event_time.astimezone(timezone.utc), e.attributes)
              for e in batch.events]
    return {"received": len(events), "inserted": c.store.add_events(events)}


# ------------------------------------------------------------------ runs

@api.post("/runs", tags=["runs"])
def trigger_run(req: RunRequest, c: Container = Depends(get_container)) -> dict[str, Any]:
    """Synchronous for simplicity; in production enqueue the job and return 202 + a run id."""
    now = utcnow()
    window = HourWindow.of(req.hour) if req.hour else HourWindow.previous(now)
    if window.end > now:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"hour {window} is not complete yet")
    if req.sources:
        unknown = set(req.sources) - set(c.catalog.sources())
        if unknown:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown sources: {sorted(unknown)}")
    statuses = c.engine.run_hour(window, req.sources)
    return {"window": str(window), "runs": [asdict(s) for s in statuses]}


@api.get("/runs", tags=["runs"])
def list_runs(hours: int = Query(24, ge=1, le=720), c: Container = Depends(get_container)) -> list[dict[str, Any]]:
    return [asdict(r) for r in c.store.list_runs(since=utcnow() - timedelta(hours=hours))]


# ------------------------------------------------------------------ alerts & errors

@api.get("/alerts", tags=["alerts"])
def list_alerts(hour: datetime | None = None, source: str | None = None, rule_id: str | None = None,
                limit: int = Query(100, ge=1, le=1000),
                c: Container = Depends(get_container)) -> list[dict[str, Any]]:
    return [asdict(a) for a in c.store.list_alerts(_hour(hour), source, rule_id, limit)]


@api.get("/errors", tags=["alerts"])
def list_errors(hour: datetime | None = None, limit: int = Query(100, ge=1, le=1000),
                c: Container = Depends(get_container)) -> list[dict[str, Any]]:
    return [asdict(d) for d in c.store.list_dead_letters(_hour(hour), limit)]


@api.get("/notifications", tags=["alerts"])
def notifications(limit: int = Query(50, ge=1, le=500), c: Container = Depends(get_container)) -> list[dict[str, Any]]:
    return [asdict(n) for n in c.inbox.recent(limit)]


# ------------------------------------------------------------------ rules

@api.get("/rules", tags=["rules"])
def list_rules(source: str | None = None, c: Container = Depends(get_container)) -> dict[str, Any]:
    return {"rules": c.catalog.configs(source), "disabled": sorted(c.store.disabled_rules())}


@api.post("/rules", status_code=status.HTTP_201_CREATED, tags=["rules"])
def upsert_rule(rule: RuleIn, c: Container = Depends(get_container)) -> dict[str, str]:
    try:
        created = c.catalog.upsert(rule.model_dump())
    except RuleConfigError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"rule_id": created.rule_id, "type": created.kind}


@api.post("/rules/{rule_id}/enable", tags=["rules"])
def enable_rule(rule_id: str, c: Container = Depends(get_container)) -> dict[str, str]:
    if not c.store.enable_rule(rule_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"rule {rule_id} is not disabled")
    return {"rule_id": rule_id, "status": "enabled"}


app.include_router(public)
app.include_router(api)
