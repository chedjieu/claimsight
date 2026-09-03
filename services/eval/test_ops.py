from __future__ import annotations

import os

os.environ.setdefault("CLAIMSIGHT_LLM_PROVIDER", "deterministic")
os.environ.setdefault("CLAIMSIGHT_FORCE_MEMORY", "1")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///./claimsight-ci.db")
os.environ.setdefault("CLAIMSIGHT_QA_SAMPLE_RATE", "0")
os.environ.setdefault("CLAIMSIGHT_VAULT_KEY", "ci-vault-key")

from pathlib import Path

from fastapi.testclient import TestClient

from claimsight_api.db import session_scope
from claimsight_api.main import app
from claimsight_api.models import ClaimRow, init_db
from claimsight_graphrag.store import _parse_list, reset_store
from claimsight_orchestrator.qa import should_qa_sample
from claimsight_phi_guard.vault import PREFIX

client = TestClient(app)


def setup_module() -> None:
    reset_store()
    init_db()


def test_phi_not_stored_plaintext():
    r = client.post("/demo/step_therapy")
    assert r.status_code == 200
    with session_scope() as db:
        row = db.get(ClaimRow, "CLM-GLP1-2026")
        assert row
        assert "078-05-1120" not in (row.notes or "")
        assert "Elena Vasquez" not in (row.notes or "")
        assert row.notes.startswith(PREFIX)
        assert "078-05-1120" not in (row.phi_mapping or "")
        assert "078-05-1120" not in (row.packet_json or "")
        assert "Elena Vasquez" not in (row.packet_json or "")
    docs = Path("data/docs")
    if docs.exists():
        for p in docs.glob("*"):
            raw = p.read_bytes()
            assert b"078-05-1120" not in raw
            assert b"Elena Vasquez" not in raw


def test_front_line_cannot_override_pending_review():
    client.post("/demo/fraud")
    denied = client.post(
        "/claims/CLM-ESI-FRAUD/decide",
        json={"action": "override_deny", "reason": "nope"},
        headers={"X-Actor": "adjuster.front"},
    )
    assert denied.status_code == 403
    ok = client.post(
        "/claims/CLM-ESI-FRAUD/decide",
        json={"action": "override_deny", "reason": "mismatch"},
        headers={"X-Actor": "reviewer.senior"},
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "denied"


def test_hydrate_and_purge_are_director_only():
    client.post("/demo/knee")
    blocked = client.get(
        "/claims/CLM-KNEE-2026?hydrate=true",
        headers={"X-Actor": "adjuster.front"},
    )
    assert blocked.status_code == 403
    hydrated = client.get(
        "/claims/CLM-KNEE-2026?hydrate=true",
        headers={"X-Actor": "director.medical"},
    )
    assert hydrated.status_code == 200
    no_purge = client.delete("/claims/CLM-KNEE-2026", headers={"X-Actor": "reviewer.senior"})
    assert no_purge.status_code == 403
    purged = client.delete("/claims/CLM-KNEE-2026", headers={"X-Actor": "director.medical"})
    assert purged.status_code == 200
    assert purged.json()["status"] == "purged"


def test_metrics_include_drift_slices():
    m = client.get("/metrics").json()
    assert "override_rate_by_cpt" in m
    assert "confidence_histogram" in m
    assert "qa_sampled" in m


def test_qa_sample_is_deterministic():
    assert should_qa_sample("x", 0) is False
    assert should_qa_sample("always", 1.0) is True
    assert should_qa_sample("CLM-GLP1-2026", 0.05) == should_qa_sample("CLM-GLP1-2026", 0.05)


def test_parse_cypher_list_payloads():
    assert _parse_list('["METF"]') == ["METF"]
    assert _parse_list(["29881"]) == ["29881"]
