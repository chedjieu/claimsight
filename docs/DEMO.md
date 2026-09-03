# ClaimSight leadership demo

**Pitch:** ClaimSight turns a five-day manual claims review into a fifteen-minute, cited, auditable AI+human decision. *AI drafts, humans decide.*

## Path (8 minutes)

1. `cp env.example .env` and `pip install -e ".[dev]"` (or `docker compose up`).
2. API: `uvicorn claimsight_api.main:app --reload` · UI: `cd apps/web && npm install && npm run dev`.
3. Open http://localhost:5173.
4. Click **Step-therapy demo**.
   - Vector search only sees “GLP-1 requires metformin failure.”
   - Graph traversal finds prior claim `CLM-PRIOR-MET` (failed metformin 11 months ago).
   - Policy + Necessity **approve**; Fraud silent; lightweight confirmation.
5. Reviewer **Approves**. Audit row + eval label written.
6. Click **Fraud demo**.
   - Dx/procedure mismatch, watchlist provider, $62k, prompt-injection in the fax.
   - PHI redacted before any model-shaped text; injection flagged; **pending human review**.
   - Front-line cannot override; switch actor to **Senior clinical** to deny.
7. Open **AI ops** for override rate by CPT, confidence histogram, token budget.
8. The subgraph panel is a live map (patient → prior claim → policy), not a JSON dump.

Do not use real PHI. All names, MRNs, and SSNs are fictional.
