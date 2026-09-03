from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from queue import Empty
from time import time
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from claimsight_api.config import settings
from claimsight_api.db import session_scope
from claimsight_api.deps import get_retriever, store_kind
from claimsight_api.events import subscribe, unsubscribe
from claimsight_api.models import AuditEvent, ClaimRow, EvalLabel, init_db
from claimsight_api.pipeline import (
    decide_claim,
    enqueue_or_run,
    ingest_claim,
    load_phi_mapping,
    purge_claim,
    run_and_store,
)
from claimsight_api.rbac import (
    decide_forbidden,
    hydrate_forbidden,
    permissions,
    profile,
    purge_forbidden,
)
from claimsight_graphrag.store import demo_payload
from claimsight_orchestrator.llm import model_name, provider_name
from claimsight_phi_guard.phi import PhiGuard
from claimsight_schemas.models import ClaimCreate, ReviewDecision
from claimsight_storage.object_store import ObjectStore

log = logging.getLogger(__name__)

DEMO_ACTORS = {
    "adjuster.front": "front-line reviewer",
    "reviewer.senior": "senior clinical reviewer",
    "director.medical": "medical director",
    "system": "system",
}

WS_CLIENTS: list[WebSocket] = []
GUARD = PhiGuard()
OBJECTS = ObjectStore()
_HITS: dict[str, deque] = defaultdict(deque)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO)
    init_db()
    get_retriever()
    yield


app = FastAPI(
    title="ClaimSight",
    version="0.1.0",
    description="AI drafts, humans decide — claims & clinical intelligence.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def actor_from(x_actor: str | None) -> str:
    name = x_actor or "adjuster.front"
    if name in DEMO_ACTORS:
        return name
    return "adjuster.front"


def _rate_ok(ip: str) -> bool:
    limit = settings.claimsight_rate_limit
    if limit <= 0:
        return True
    now = time()
    q = _HITS[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= limit:
        return False
    q.append(now)
    return True


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if request.method == "POST":
        host = request.client.host if request.client else "local"
        if not _rate_ok(host):
            return JSONResponse({"detail": "rate limited"}, status_code=429)
    return await call_next(request)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "env": settings.claimsight_env,
        "graph": store_kind(),
        "llm": provider_name(),
        "model": model_name(),
        "storage": OBJECTS.kind,
        "tagline": "AI drafts, humans decide",
    }


@app.post("/claims")
def create_claim(body: ClaimCreate, x_actor: str | None = Header(default=None)) -> dict[str, Any]:
    actor = actor_from(x_actor)
    data = body.model_dump()
    run_now = data.pop("run_immediately")
    if not data.get("id"):
        data["id"] = f"CLM-{uuid4().hex[:10]}"
    ingest_claim(data, actor=actor)
    if run_now:
        enqueue_or_run(data["id"], actor=actor)
    return {"claim_id": data["id"]}


@app.post("/demo/{name}")
def fire_demo(name: str, x_actor: str | None = Header(default=None)) -> dict[str, Any]:
    actor = actor_from(x_actor)
    try:
        data = demo_payload(name)
    except KeyError:
        raise HTTPException(404, f"unknown demo {name}; try step_therapy, knee, fraud") from None
    ingest_claim(data, actor=actor)
    run_and_store(data["id"], actor=actor)
    return {"claim_id": data["id"]}


@app.get("/claims")
def list_claims(
    status: str | None = None, x_actor: str | None = Header(default=None)
) -> list[dict[str, Any]]:
    actor = actor_from(x_actor)
    with session_scope() as db:
        q = db.query(ClaimRow).order_by(ClaimRow.ingested_at.desc())
        if status:
            q = q.filter(ClaimRow.status == status)
        rows = q.limit(100).all()
        return [_claim_summary(r, actor) for r in rows]


@app.get("/claims/{claim_id}")
def get_claim(
    claim_id: str,
    hydrate: bool = False,
    x_actor: str | None = Header(default=None),
) -> dict[str, Any]:
    actor = actor_from(x_actor)
    hydrated = False
    with session_scope() as db:
        row = db.get(ClaimRow, claim_id)
        if not row:
            raise HTTPException(404, "claim not found")
        packet = json.loads(row.packet_json or "{}")
        mapping = load_phi_mapping(row)
        if hydrate:
            denied = hydrate_forbidden(actor)
            if denied:
                raise HTTPException(403, denied)
            if mapping:
                notes = packet.get("redacted_notes") or ""
                packet["hydrated_notes_preview"] = GUARD.rehydrate(notes, mapping)
            hydrated = True
        payload = {
            **_claim_summary(row, actor),
            "packet": packet,
            "model_name": row.model_name,
            "prompt_version": row.prompt_version,
            "decided_by": row.decided_by,
            "decided_at": row.decided_at.isoformat() if row.decided_at else None,
            "token_used": row.token_used,
        }
    if hydrated:
        from claimsight_api.pipeline import audit

        audit(actor, "hydrate", claim_id, reason="break-glass re-identification")
    return payload


@app.post("/claims/{claim_id}/decide")
def decide(
    claim_id: str, body: ReviewDecision, x_actor: str | None = Header(default=None)
) -> dict[str, Any]:
    actor = actor_from(x_actor)
    with session_scope() as db:
        row = db.get(ClaimRow, claim_id)
        if not row:
            raise HTTPException(404, "claim not found")
        denied = decide_forbidden(actor, body.action, row.status)
        if denied:
            raise HTTPException(403, denied)
    try:
        return decide_claim(
            claim_id,
            action=body.action,
            actor=actor,
            reason=body.reason,
            edited_recommendation=body.edited_recommendation,
            edited_narrative=body.edited_narrative,
        )
    except KeyError:
        raise HTTPException(404, "claim not found") from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.delete("/claims/{claim_id}")
def delete_claim(claim_id: str, x_actor: str | None = Header(default=None)) -> dict[str, Any]:
    actor = actor_from(x_actor)
    denied = purge_forbidden(actor)
    if denied:
        raise HTTPException(403, denied)
    try:
        return purge_claim(claim_id, actor)
    except KeyError:
        raise HTTPException(404, "claim not found") from None


@app.get("/review-queue")
def review_queue(x_actor: str | None = Header(default=None)) -> list[dict[str, Any]]:
    actor = actor_from(x_actor)
    with session_scope() as db:
        rows = (
            db.query(ClaimRow)
            .filter(ClaimRow.status.in_(["ready_for_confirmation", "pending_human_review"]))
            .order_by(ClaimRow.ingested_at.desc())
            .all()
        )
        return [_claim_summary(r, actor) for r in rows]


@app.get("/audit")
def list_audit(entity_id: str | None = None, limit: int = 80) -> list[dict[str, Any]]:
    with session_scope() as db:
        q = db.query(AuditEvent).order_by(AuditEvent.ts.desc())
        if entity_id:
            q = q.filter(AuditEvent.entity_id == entity_id)
        return [
            {
                "id": e.id,
                "ts": e.ts.isoformat() if e.ts else None,
                "actor": e.actor,
                "action": e.action,
                "entity_type": e.entity_type,
                "entity_id": e.entity_id,
                "reason": e.reason,
            }
            for e in q.limit(limit).all()
        ]


@app.get("/metrics")
def metrics() -> dict[str, Any]:
    with session_scope() as db:
        rows = db.query(ClaimRow).all()
        labels = db.query(EvalLabel).all()
        n = len(rows) or 1
        statuses: dict[str, int] = {}
        confs: list[float] = []
        tokens = 0
        by_cpt: dict[str, dict[str, int]] = defaultdict(lambda: {"n": 0, "overrides": 0})
        buckets = {"<0.5": 0, "0.5-0.7": 0, "0.7-0.9": 0, ">=0.9": 0}
        qa = 0
        for r in rows:
            statuses[r.status] = statuses.get(r.status, 0) + 1
            conf = r.confidence or 0
            confs.append(conf)
            tokens += r.token_used or 0
            if conf < 0.5:
                buckets["<0.5"] += 1
            elif conf < 0.7:
                buckets["0.5-0.7"] += 1
            elif conf < 0.9:
                buckets["0.7-0.9"] += 1
            else:
                buckets[">=0.9"] += 1
            packet = json.loads(r.packet_json or "{}")
            if packet.get("qa_sampled"):
                qa += 1
            key = ",".join(json.loads(r.cpt or "[]") or ["unknown"])
            by_cpt[key]["n"] += 1
        override_ids = {l.claim_id for l in labels if l.override}
        for r in rows:
            key = ",".join(json.loads(r.cpt or "[]") or ["unknown"])
            if r.id in override_ids:
                by_cpt[key]["overrides"] += 1
        overrides = sum(1 for l in labels if l.override)
        decided = sum(1 for r in rows if r.status in {"approved", "denied", "escalated"})
        override_rate_by_cpt = {
            k: round(v["overrides"] / max(v["n"], 1), 3) for k, v in by_cpt.items()
        }
        return {
            "claim_count": len(rows),
            "status_counts": statuses,
            "override_rate": overrides / max(len(labels), 1),
            "override_rate_by_cpt": override_rate_by_cpt,
            "confidence_histogram": buckets,
            "qa_sampled": qa,
            "mean_confidence": round(sum(confs) / n, 3),
            "mean_tokens": round(tokens / n, 1),
            "decided": decided,
            "queue_depth": statuses.get("pending_human_review", 0)
            + statuses.get("ready_for_confirmation", 0),
            "graph": store_kind(),
            "llm": provider_name(),
        }


@app.get("/events")
async def sse() -> StreamingResponse:
    q = subscribe()

    async def gen():
        try:
            yield 'data: {"event":"hello"}\n\n'
            while True:
                try:
                    event = q.get_nowait()
                    yield f"data: {json.dumps(event)}\n\n"
                except Empty:
                    await asyncio.sleep(0.4)
                    yield ": ping\n\n"
        finally:
            unsubscribe(q)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.websocket("/ws/queue")
async def ws_queue(ws: WebSocket) -> None:
    await ws.accept()
    WS_CLIENTS.append(ws)
    q = subscribe()
    try:
        await ws.send_json({"ok": True, "event": "hello"})
        while True:
            try:
                event = q.get_nowait()
                await ws.send_json(event)
            except Empty:
                await asyncio.sleep(0.4)
                try:
                    await asyncio.wait_for(ws.receive_text(), timeout=0.01)
                except TimeoutError:
                    pass
    except WebSocketDisconnect:
        pass
    finally:
        unsubscribe(q)
        if ws in WS_CLIENTS:
            WS_CLIENTS.remove(ws)


def _claim_summary(r: ClaimRow, actor: str = "adjuster.front") -> dict[str, Any]:
    packet = json.loads(r.packet_json or "{}")
    provider = (packet.get("subgraph") or {}).get("provider") or {}
    return {
        "id": r.id,
        "patient_id": r.patient_id,
        "provider_id": r.provider_id,
        "icd10": json.loads(r.icd10 or "[]"),
        "cpt": json.loads(r.cpt or "[]"),
        "amount_usd": r.amount_usd,
        "service_date": r.service_date,
        "status": r.status,
        "recommendation": r.recommendation,
        "confidence": r.confidence,
        "route": r.route,
        "qa_sampled": bool(packet.get("qa_sampled")),
        "specialty": provider.get("specialty"),
        "permissions": permissions(actor, r.status),
        "actor_tier": profile(actor)["label"],
        "ingested_at": r.ingested_at.isoformat() if r.ingested_at else None,
    }


def run() -> None:
    import uvicorn

    uvicorn.run("claimsight_api.main:app", host="0.0.0.0", port=8000, reload=True)
