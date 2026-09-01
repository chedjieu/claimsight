from __future__ import annotations

import os

os.environ.setdefault("CLAIMSIGHT_LLM_PROVIDER", "deterministic")
os.environ.setdefault("CLAIMSIGHT_FORCE_MEMORY", "1")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///./claimsight-ci.db")

from fastapi.testclient import TestClient

from claimsight_api.main import app
from claimsight_api.models import init_db
from claimsight_graphrag.store import reset_store


client = TestClient(app)


def setup_module() -> None:
    reset_store()
    init_db()


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["tagline"]


def test_demo_step_therapy_and_decide():
    r = client.post("/demo/step_therapy", headers={"X-Actor": "adjuster.front"})
    assert r.status_code == 200
    cid = r.json()["claim_id"]
    detail = client.get(f"/claims/{cid}").json()
    assert detail["recommendation"] == "approve"
    assert detail["packet"]["findings"]
    decide = client.post(
        f"/claims/{cid}/decide",
        json={"action": "approve", "reason": "step therapy documented"},
        headers={"X-Actor": "reviewer.senior"},
    )
    assert decide.status_code == 200
    assert decide.json()["status"] == "approved"
    audit = client.get("/audit").json()
    assert any(a["action"].startswith("decide") for a in audit)


def test_metrics_and_queue():
    client.post("/demo/knee")
    q = client.get("/review-queue")
    assert q.status_code == 200
    m = client.get("/metrics")
    assert m.status_code == 200
    assert m.json()["claim_count"] >= 1
