# services/eval — gold sets and CI gates

```bash
CLAIMSIGHT_LLM_PROVIDER=deterministic CLAIMSIGHT_FORCE_MEMORY=1 pytest -q
```

| File | Layer |
|---|---|
| `test_retrieval.py` | vector vs GraphRAG (step-therapy miss) |
| `test_pipeline.py` | supervisor recommendations |
| `test_trajectory.py` | Necessity never `write_graph` |
| `test_security.py` | PHI leak + injection + vault |
| `test_ops.py` | encryption at rest, RBAC, purge, drift metrics |
| `test_ragas.py` | citation faithfulness proxy |
| `test_llm_judge.py` | skipped without API key |
| `test_api.py` | FastAPI HITL loop |
| `apps/web/e2e` | Playwright review-desk walkthrough |

Gold JSON under `gold/`. GitHub Actions: `.github/workflows/ci.yml`.

## What this is not

The RAGAS PyPI package is not vendored. LLM-judge is not CI ground truth.
