from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from claimsight_api.config import settings
from claimsight_api.db import session_scope
from claimsight_api.deps import get_retriever, store_kind
from claimsight_api.models import AuditEvent, ClaimRow, EvalLabel, init_db
from claimsight_api.pipeline import decide_claim, ingest_claim, run_and_store
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


async def broadcast(event: dict[str, Any]) -> None:
    dead = []
    for ws in WS_CLIENTS:
        try:
            await ws.send_json(event)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in WS_CLIENTS:
            WS_CLIENTS.remove(ws)


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
        run_and_store(data["id"], actor=actor)
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
def list_claims(status: str | None = None) -> list[dict[str, Any]]:
    with session_scope() as db:
        q = db.query(ClaimRow).order_by(ClaimRow.ingested_at.desc())
        if status:
            q = q.filter(ClaimRow.status == status)
        rows = q.limit(100).all()
        return [_claim_summary(r) for r in rows]


@app.get("/claims/{claim_id}")
def get_claim(claim_id: str, hydrate: bool = False) -> dict[str, Any]:
    with session_scope() as db:
        row = db.get(ClaimRow, claim_id)
        if not row:
            raise HTTPException(404, "claim not found")
        packet = json.loads(row.packet_json or "{}")
        mapping = json.loads(row.phi_mapping or "{}")
        if hydrate and mapping:
            notes = packet.get("redacted_notes") or ""
            packet["hydrated_notes_preview"] = GUARD.rehydrate(notes, mapping)
        return {
            **_claim_summary(row),
            "packet": packet,
            "model_name": row.model_name,
            "prompt_version": row.prompt_version,
            "decided_by": row.decided_by,
            "decided_at": row.decided_at.isoformat() if row.decided_at else None,
            "token_used": row.token_used,
        }


@app.post("/claims/{claim_id}/decide")
def decide(claim_id: str, body: ReviewDecision, x_actor: str | None = Header(default=None)) -> dict[str, Any]:
    actor = actor_from(x_actor)
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


@app.get("/review-queue")
def review_queue() -> list[dict[str, Any]]:
    with session_scope() as db:
        rows = (
            db.query(ClaimRow)
            .filter(ClaimRow.status.in_(["ready_for_confirmation", "pending_human_review"]))
            .order_by(ClaimRow.ingested_at.desc())
            .all()
        )
        return [_claim_summary(r) for r in rows]


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
        for r in rows:
            statuses[r.status] = statuses.get(r.status, 0) + 1
            confs.append(r.confidence or 0)
            tokens += r.token_used or 0
        overrides = sum(1 for l in labels if l.override)
        decided = sum(1 for r in rows if r.status in {"approved", "denied", "escalated"})
        return {
            "claim_count": len(rows),
            "status_counts": statuses,
            "override_rate": overrides / max(len(labels), 1),
            "mean_confidence": round(sum(confs) / n, 3),
            "mean_tokens": round(tokens / n, 1),
            "decided": decided,
            "queue_depth": statuses.get("pending_human_review", 0)
            + statuses.get("ready_for_confirmation", 0),
            "graph": store_kind(),
            "llm": provider_name(),
        }


@app.websocket("/ws/queue")
async def ws_queue(ws: WebSocket) -> None:
    await ws.accept()
    WS_CLIENTS.append(ws)
    try:
        await ws.send_json({"ok": True, "event": "hello"})
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        if ws in WS_CLIENTS:
            WS_CLIENTS.remove(ws)


def _claim_summary(r: ClaimRow) -> dict[str, Any]:
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
        "ingested_at": r.ingested_at.isoformat() if r.ingested_at else None,
    }


def run() -> None:
    import uvicorn

    uvicorn.run("claimsight_api.main:app", host="0.0.0.0", port=8000, reload=True)
