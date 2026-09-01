# packages/schemas — shared Pydantic models

`ClaimCreate`, `ClaimRecord`, `AgentFinding`, `Citation`, `RecommendationPacket`, `ReviewDecision`.

Imported by API, orchestrator, and evals so contracts cannot drift.

```python
from claimsight_schemas import ClaimCreate
```

## What this is not

Not an OpenAPI generator (FastAPI builds that from these models).
