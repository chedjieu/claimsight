# ClaimSight
### An End-to-End, Multi-Agent GenAI Platform for Claims & Clinical Intelligence
**Capstone Project — Full Narrative, Architecture, and Production Design**

---

## 1. Executive Narrative

Every day, health insurers and payers process thousands of claims. Behind each one sits a pile of unstructured evidence — clinical notes, faxed prior-authorization forms, lab PDFs, provider letters — that a human adjuster must read, cross-reference against policy language, medical necessity guidelines, and the patient's own history, and then decide: **approve, deny, or escalate**.

This process is slow (days), inconsistent (different adjusters reach different conclusions on similar claims), expensive (skilled clinical reviewers doing document triage), and opaque (denials are hard to explain or defend in an audit).

**ClaimSight** is a production-grade GenAI platform that compresses this cycle from days to minutes — without removing humans from decisions that matter. It reads every document, builds a living knowledge graph of patients, providers, diagnoses, procedures, and policies, reasons over that graph with a team of specialist AI agents supervised by an orchestrator, and produces a fully-cited recommendation. Anything uncertain, high-value, or high-risk is automatically routed to a human clinical reviewer — with the AI's full evidence trail attached, not a black box.

**The pitch to a business leader in one sentence:** *ClaimSight turns a five-day, error-prone manual claims review into a fifteen-minute, evidence-backed, auditable AI+human decision — cutting review cost, improving consistency, and creating a defensible compliance trail, without ever letting an AI make an unsupervised clinical judgment.*

This same architecture generalizes far beyond insurance — it is a blueprint for *any* regulated, document-heavy, high-stakes decision workflow (underwriting, loan adjudication, regulatory filing review, clinical trial eligibility, procurement compliance). Insurance claims is simply the sharpest, most relatable version of the story.

---

## 2. The Business Case

| Stakeholder | Pain today | ClaimSight value |
|---|---|---|
| Claims adjuster | Manually reads 20–50 pages per claim; juggles policy PDFs, EHR excerpts, prior claims | Gets a synthesized, cited recommendation in minutes; reviews instead of researches |
| Chief Medical Officer | Inconsistent necessity determinations create legal and clinical risk | Every decision traces to specific guideline text and graph relationships — fully auditable |
| Compliance/Legal | PHI exposure risk when documents move between systems and vendors (incl. LLM vendors) | PHI/PII is detected and redacted *before* anything reaches a model API; full audit log |
| CFO | Cost per claim reviewed; claim backlog interest/penalties | 60–80% of claims resolved with AI-drafted + human-approved decisions; backlog collapses |
| CIO/CTO | "AI project" fear: hallucination, vendor lock-in, unbounded cost | Model-agnostic (Pydantic AI abstraction), fully observable, evaluated continuously, human veto on every low-confidence case |

**Illustrative ROI framing** (numbers are illustrative for the pitch, not a guarantee): if average manual review costs $40 and takes 3 days, and ClaimSight auto-drafts 70% of claims for a 5-minute human confirm at $6 marginal cost, a payer processing 500,000 claims/year saves on the order of $10–15M annually while cutting cycle time by >90%. This is the slide business leaders remember.

---

## 3. Product Narrative — A Claim's Journey Through ClaimSight

1. **Intake.** A claim arrives via API/portal upload: structured claim fields (CPT/ICD codes, dates, amounts) plus attached documents (clinical notes, prior-auth PDFs, sometimes scanned faxes).
2. **De-identification.** Before any document touches an LLM, the **Intake & Redaction Agent** OCRs scanned pages, extracts structured fields, and runs PHI/PII detection — names, MRNs, SSNs, dates of birth are tokenized/redacted, with a secure re-identification map kept in an encrypted vault, never sent to the model layer.
3. **Understanding.** The **Entity & Coding Agent** extracts diagnoses, procedures, and provider/patient relationships and writes them into the **Neo4j knowledge graph**, linking this claim to the patient's history, the provider's pattern of billing, and the relevant policy nodes.
4. **Retrieval.** The **GraphRAG Retrieval Agent** runs a hybrid query: graph traversal (e.g., "what prior treatments has this patient had for this diagnosis, and what does the policy say about step therapy") *plus* vector semantic search over the guideline/policy corpus (pgvector) — combining relational precision with semantic recall.
5. **Parallel Reasoning.** The **Supervisor Agent** (built in LangGraph) fans work out to three specialist agents *in parallel*: Policy & Coverage, Medical Necessity, and Fraud/Anomaly Detection. Each returns a structured, cited finding.
6. **Synthesis & Confidence Scoring.** The Supervisor fans results back in, synthesizes a recommendation, and computes a confidence score from agent agreement, evidence strength, and anomaly flags.
7. **Human-in-the-Loop Gate.** If confidence is high and no risk flags fired, the recommendation is queued for a lightweight human confirmation. If confidence is low, agents disagree, or the Fraud agent flags anomalies, the graph **interrupts** and routes to a specialist human reviewer with the complete evidence trail, graph visualization, and each agent's reasoning.
8. **Decision & Feedback.** The human approves, edits, or overrides. That decision — and any edit — is captured as labeled feedback that feeds the continuous evaluation and prompt/guideline-refinement pipeline.
9. **Audit.** Every step (model calls, retrieved evidence, redactions performed, human overrides) is logged immutably for compliance review.

---

## 4. High-Level Architecture

See the accompanying diagram (`claimsight-high-level-architecture`). In text form, the layers are:

- **Experience layer:** React (Vite + TS) adjuster console and ops dashboard; FastAPI-driven OpenAPI docs for internal tooling.
- **API layer:** FastAPI — auth'd, rate-limited entry point; enqueues work rather than blocking on inference.
- **Orchestration layer:** LangGraph Supervisor graph, calling LangChain-wrapped tools/retrievers and Pydantic AI-typed agent calls.
- **Agent layer:** Specialist agents (Intake/Redaction, Entity/Coding, GraphRAG Retrieval, Policy & Coverage, Medical Necessity, Fraud/Anomaly, Compliance/PHI-guard).
- **Data layer:** Neo4j (knowledge graph), Postgres+pgvector via Supabase (documents, embeddings, hybrid search, structured claim data), Object storage (raw documents, encrypted).
- **Model layer:** Anthropic Claude (primary reasoning), OpenAI (embeddings/secondary), abstracted behind Pydantic AI so providers are swappable without touching agent logic.
- **Human-in-the-loop layer:** Review queue service + UI, fed by LangGraph interrupts; decisions written back to the data layer and eval store.
- **Cross-cutting plane:** Security/PHI guardrails, observability (LangSmith/Langfuse, Sentry, PostHog), evaluation harness (RAGAS + custom + LLM-judge + guardrail red-team), CI/CD.

---

## 5. Low-Level Architecture — Component Detail

### 5.1 Monorepo structure (extending the video's `api / web / worker` pattern)

```
claimsight/
├── apps/
│   ├── web/                 # React + Vite + TS — adjuster console, ops dashboard
│   └── api/                 # FastAPI — REST + WebSocket for review queue updates
├── services/
│   ├── orchestrator/        # LangGraph graphs: supervisor + specialist agent nodes
│   ├── worker/               # Celery workers: OCR, embeddings, long-running agent runs
│   ├── graphrag/             # Neo4j client, graph schema, Cypher query templates
│   ├── phi_guard/            # PII/PHI detection, redaction, re-identification vault
│   └── eval/                 # RAGAS + custom evals, guardrail red-team suite, CI hooks
├── packages/
│   ├── schemas/              # Shared Pydantic models (claim, agent I/O, graph entities)
│   └── prompts/              # Versioned prompt/guideline templates (git-tracked)
├── infra/
│   ├── terraform/            # Cloud infra as code
│   └── github-actions/       # CI/CD pipelines
└── docs/
    └── architecture/         # ADRs, diagrams
```

### 5.2 Data flow for one claim (sequence)

1. `POST /claims` (FastAPI) → validates payload → writes claim row (status=`queued`) → publishes job to Redis.
2. Celery worker picks up job → OCR (if needed) → Intake/Redaction Agent runs → writes de-identified text + structured fields to Postgres, raw file to encrypted object storage.
3. Worker invokes the **LangGraph orchestrator** as a durable, checkpointed run (LangGraph's persistence layer means a HITL pause can survive hours/days without holding a worker thread).
4. Entity/Coding Agent upserts graph nodes/edges in Neo4j (`Patient`, `Provider`, `Diagnosis`, `Procedure`, `Claim`, `PriorAuth`, `PolicyClause`, `Guideline`).
5. Supervisor fans out to Policy & Coverage, Medical Necessity, Fraud/Anomaly agents **in parallel** (LangGraph parallel branches) — each does its own GraphRAG retrieval scoped to its question.
6. Supervisor fans in, computes confidence, and either:
   - writes `status=ready_for_confirmation` (high confidence), or
   - triggers a LangGraph **interrupt** → `status=pending_human_review`, pushes to review queue with WebSocket notification to the console.
7. Human decision (approve/override) → written to Postgres + Neo4j (as a `Decision` node linked to the claim) → emitted as an evaluation-labeled event.
8. All model calls, tool calls, retrieved chunks, and redactions are traced (LangSmith/Langfuse) and written to an append-only audit log table.

### 5.3 GraphRAG design (Neo4j)

**Core node types:** `Patient`, `Provider`, `Claim`, `Diagnosis(ICD-10)`, `Procedure(CPT)`, `PolicyClause`, `Guideline`, `PriorAuth`, `Decision`.

**Key relationships:** `(Patient)-[:HAS_DIAGNOSIS]->(Diagnosis)`, `(Claim)-[:FOR_PROCEDURE]->(Procedure)`, `(Procedure)-[:REQUIRES]->(PolicyClause)`, `(Diagnosis)-[:GOVERNED_BY]->(Guideline)`, `(Provider)-[:BILLED]->(Claim)`, `(Claim)-[:PRIOR_CLAIM_OF]->(Claim)` (temporal history chains), `(Decision)-[:MADE_FOR]->(Claim)`.

**Why graph + vector (GraphRAG), not just vector RAG:** vector search alone tells you *"here's a similar-sounding guideline paragraph."* Graph traversal tells you *"this exact patient already tried and failed the required first-line treatment eleven months ago under this exact policy clause"* — a precise, explainable, multi-hop fact vector similarity cannot reliably reconstruct. ClaimSight uses graph traversal for **relational/precedent facts** and vector search for **semantic guideline retrieval**, then merges both into the agent's context — this hybrid is the actual "GraphRAG" pattern, not graph-*or*-vector.

### 5.4 Multi-agent orchestration (LangGraph + LangChain)

See the second diagram (`claimsight-agent-orchestration`). Design principles:

- **Supervisor pattern:** one LangGraph "supervisor" node owns routing, fan-out/fan-in, confidence scoring, and the HITL decision — specialist agents never talk to each other directly, which keeps the system debuggable and keeps blast radius small if one agent misbehaves.
- **Parallel execution:** Policy & Coverage, Medical Necessity, and Fraud/Anomaly agents run concurrently as independent LangGraph branches once Entity/Coding has populated the graph — this is what keeps end-to-end latency in the minutes range rather than serial-chaining every agent.
- **Typed I/O everywhere:** every agent's input/output is a Pydantic AI model (not free text), so the Supervisor can programmatically check agreement, confidence, and citation completeness instead of re-parsing prose.
- **Durable, resumable state:** LangGraph's checkpointer persists graph state to Postgres, so a human-in-the-loop interrupt can sit for hours/days and resume exactly where it paused — critical for a real review workflow, not a demo.
- **Tool use via LangChain:** each agent gets a narrow, explicit toolbelt (e.g., the Medical Necessity agent can call `graph_traverse_history`, `vector_search_guidelines`, but *not* `write_graph` — write access is isolated to the Entity/Coding agent) — least-privilege by design.

---

## 6. Human-in-the-Loop Design

Human review is not a fallback bolted on at the end — it's a first-class state in the LangGraph state machine.

- **Interrupt triggers:** confidence below threshold; inter-agent disagreement (e.g., Policy says approve, Fraud flags anomaly); claim value above a configurable dollar threshold; any claim touching a "sensitive" diagnosis category requiring mandatory review; random sampling for QA (e.g., 5% of even high-confidence claims, to catch drift).
- **Reviewer experience:** the console shows the AI's recommendation, per-agent reasoning and citations, a graph visualization of the relevant patient/policy subgraph, and the exact redacted/re-identified source passages — the reviewer is auditing evidence, not trusting a black-box score.
- **Feedback loop:** every human edit or override is stored as a labeled example. These feed (a) the nightly evaluation regression suite, (b) a backlog for prompt/guideline refinement, and (c) — longer-term — optional fine-tuning or few-shot example curation.
- **Escalation tiers:** front-line reviewer → senior clinical reviewer → medical director, mirroring real payer review hierarchies, each tier able to see everything the tier below saw.

---

## 7. Security, Privacy, and PHI/PII

Treated as a first-class subsystem (`services/phi_guard`), not an afterthought:

- **De-identification before inference:** Presidio-style NER + regex/pattern detectors identify PHI/PII (names, MRNs, SSNs, DOB, addresses, phone/email) in both structured fields and free text; detected spans are tokenized (`[PATIENT_NAME_1]`) before any content is sent to an LLM provider. A separate, tightly access-controlled **re-identification vault** maps tokens back to real values only for authorized, audited operations (e.g., rendering the reviewer UI).
- **Encryption:** AES-256 at rest for documents and the re-id vault; TLS in transit everywhere; field-level encryption for the most sensitive Postgres columns.
- **Access control:** OIDC-based auth (Supabase Auth / Auth0 / Keycloak) with RBAC *and* ABAC — e.g., a reviewer can only see claims in their assigned queue and specialty; break-glass access is logged and time-boxed.
- **Model-provider isolation:** no raw PHI ever leaves the redaction boundary; if a provider requires a BAA (Business Associate Agreement) for HIPAA compliance, that's a hard gating requirement on vendor selection — documented as an explicit compliance checklist, not assumed.
- **Prompt-injection / data-exfiltration guardrails:** a dedicated **Compliance/PHI-guard agent** reviews every outbound agent response before it's shown to a human or written to the graph, checking for (a) leaked PII/PHI tokens that shouldn't be there, (b) injected instructions from document content attempting to alter agent behavior, (c) out-of-scope claims (e.g., an agent asserting something no retrieved evidence supports).
- **Audit trail:** every model call, tool call, retrieval, redaction, and human decision is written to an append-only audit log (who/what/when/why), aligned to SOC 2 and HIPAA audit requirements.
- **Data retention & right-to-delete:** configurable retention windows per data class, with a deletion workflow that also purges vector/graph derivatives, not just the source row — a detail that's easy to miss and important to call out to compliance stakeholders.

---

## 8. Evaluation Strategy (Multiple Layers)

A GenAI capstone earns its "production-ready" claim through its eval story, not its demo. ClaimSight evaluates at four layers:

1. **Retrieval quality (RAGAS-style):** faithfulness (is the answer grounded in retrieved evidence?), answer relevancy, context precision/recall — run against a curated golden set of claim scenarios with known-correct outcomes, both for the vector leg and the graph-traversal leg of GraphRAG.
2. **Agent-trajectory evaluation:** did each agent call the *right* tools, in a reasonable order, and stay within its scoped toolbelt? Evaluated via LangSmith/Langfuse trace analysis plus custom assertions (e.g., "Medical Necessity agent must never call `write_graph`").
3. **LLM-as-judge with rubric-based scoring:** an independent judge model scores each final recommendation against a rubric (citation completeness, clinical soundness of reasoning, appropriate escalation decisions) — used for regression testing in CI, not as ground truth by itself.
4. **Guardrail / red-team evaluation:** an adversarial test suite (prompt-injection attempts embedded in fake documents, PHI-leakage probes, jailbreak attempts) run against the Compliance agent and the pipeline as a whole, on a schedule and on every prompt/model change.
5. **Human feedback as live evaluation:** reviewer overrides are treated as continuous production evaluation signal — override rate by claim type/agent is a first-class dashboard metric, and a rising override rate on a given agent is itself an alert.
6. **Drift monitoring:** embedding-space and confidence-score distribution monitoring to catch silent model or data drift between evaluation cycles.

All of this runs in CI (`services/eval`) on every prompt, model, or graph-schema change, plus nightly against production traffic samples — the eval suite is versioned alongside prompts in `packages/prompts`, so a prompt change and its eval regression are reviewed together in one PR.

---

## 9. Technology Stack

| Layer | Technology | Why |
|---|---|---|
| Frontend | React (Vite) + TypeScript, Tailwind, shadcn/ui | Modern, fast DX; matches the video's front-end choice, extended for an enterprise console |
| Backend API | FastAPI | Async, auto-generated OpenAPI docs, strong typing — directly from the source stack |
| Agent orchestration | **LangGraph** (stateful graphs, checkpointing, interrupts) + **LangChain** (tools, retrievers) | LangGraph gives durable, resumable multi-agent state machines with native HITL interrupts; LangChain supplies the tool/retriever ecosystem |
| Agent typed I/O | **Pydantic AI** | Keeps the "AI SDK"-like universal, typed, multi-provider interface from the original video, now used for structured agent contracts, not just single calls |
| Multi-agent pattern | Supervisor + parallel specialist agents | Debuggable, least-privilege, and fast (fan-out/fan-in) vs. one monolithic agent |
| Knowledge graph / GraphRAG | **Neo4j** | Native graph traversal for multi-hop relational facts (patient history, policy chains) that vector search alone can't reliably reconstruct |
| Vector store & hybrid search | Postgres + pgvector via **Supabase** | Keeps the video's proven hybrid keyword+semantic search pattern; also houses structured claim data |
| ORM / migrations | SQLAlchemy + Alembic | Type-safe DB access and schema migrations |
| Background jobs / queue | Redis + Celery | Async OCR, embedding generation, and long-running agent runs, exactly as demonstrated in the source video |
| Model providers | Anthropic Claude (primary reasoning), OpenAI (embeddings/secondary) | Abstracted behind Pydantic AI so the platform is not locked to one vendor |
| PHI/PII detection | Presidio-style NER + regex, custom clinical-entity rules | De-identifies before any model call |
| AuthN/AuthZ | OIDC (Auth0/Keycloak or Supabase Auth) + RBAC/ABAC | Enterprise-grade access control |
| Observability / tracing | LangSmith or Langfuse, Sentry, PostHog | Full agent trace visibility, error monitoring, product analytics |
| Evaluation | RAGAS, custom trajectory evals, LLM-as-judge, guardrail red-team (e.g., NeMo Guardrails / Llama Guard patterns) | Multi-layer eval as described in §8 |
| Testing | pytest, pytest-playwright | Backend unit/integration + e2e browser testing |
| CI/CD | GitHub Actions, Terraform | Automated pipelines and infra-as-code, staged environments |
| Hosting | Frontend: Vercel · API/workers: Cloud Run or Fly.io · Redis: Upstash/Elasticache · Neo4j: Neo4j Aura (managed) · Supabase (managed Postgres) | Managed services where possible to reduce ops burden while remaining cloud-portable |
| Secrets | Doppler / cloud secrets manager | Centralized, environment-scoped secrets |

---

## 10. Deployment, CI/CD, and Observability

- **Environments:** dev → staging → prod, each with isolated Neo4j/Postgres/Redis instances; staging runs the full eval suite against synthetic PHI-free claim fixtures before any prod promotion.
- **CI/CD (GitHub Actions):** on PR — lint, type-check, unit tests, e2e (Playwright), prompt/eval regression suite; on merge to `main` — deploy to staging, run full eval + guardrail red-team suite, require sign-off gate before prod promotion (a deliberate human-in-the-loop for the *pipeline itself*, mirroring the product's own philosophy).
- **Observability:** every agent run is traced end-to-end (LangSmith/Langfuse) with token/cost/latency breakdown per agent; Sentry for exceptions; PostHog for adjuster/reviewer product usage; a dedicated "AI Ops" dashboard surfaces confidence-score distributions, override rates, and guardrail trigger rates as the primary health signals — not just uptime.
- **Cost governance:** per-claim cost budget enforced at the Supervisor level (a cap on total tokens/tool calls before forcing an HITL escalation) — a detail business leaders specifically respond well to, since "unbounded AI spend" is a common fear.

---

## 11. Phased Delivery Roadmap

| Phase | Scope | Outcome |
|---|---|---|
| 0 — Foundations | Monorepo, FastAPI + React skeleton, Postgres/pgvector via Supabase, Redis/Celery queue, basic claim intake | Working, boring, reliable plumbing |
| 1 — Single-agent RAG | One retrieval agent (vector-only), manual review of every claim | Prove document understanding + retrieval quality |
| 2 — GraphRAG | Stand up Neo4j, entity extraction, hybrid graph+vector retrieval | Prove relational reasoning beats vector-only |
| 3 — Multi-agent + Supervisor | LangGraph supervisor, parallel specialist agents, typed I/O via Pydantic AI | Prove orchestration, parallelism, and confidence scoring |
| 4 — Human-in-the-loop | Interrupts, review queue, reviewer console, feedback capture | Prove the AI+human loop, not AI-alone |
| 5 — Security & Compliance | PHI/PII redaction pipeline, RBAC/ABAC, audit log, encryption | Prove enterprise readiness |
| 6 — Evaluation & Guardrails | RAGAS, trajectory evals, LLM-judge, red-team suite, CI gating | Prove the system is measurably trustworthy, continuously |
| 7 — Scale & Ops | Observability dashboards, cost governance, drift monitoring, multi-region | Prove production sustainability |

This phasing doubles as the presentation structure for business leaders: each phase has a demoable milestone and a plain-English "what risk did this retire" story.

---

## 12. Key Talking Points for a Global Business Audience

- **"AI drafts, humans decide"** — the single sentence that defuses most executive anxiety about GenAI in regulated decisions.
- **Every recommendation is a citation trail, not a guess** — GraphRAG's multi-hop precedent facts plus vector-grounded guideline text make each decision explainable in an audit or a lawsuit.
- **PHI never reaches a model unredacted** — a concrete, demonstrable answer to the first question every compliance officer will ask.
- **The system is model-agnostic** — Pydantic AI's abstraction means switching or mixing model vendors is a config change, not a rewrite; addresses vendor-lock-in fear directly.
- **Evaluation is continuous, not a one-time demo** — nightly regression, red-teaming, and live override-rate monitoring mean quality is a measured, trending number leadership can track like any other KPI.
- **The pattern generalizes** — swap "claims" for "underwriting," "loan review," or "regulatory filing," and the same supervisor/specialist-agent/GraphRAG/HITL/eval skeleton applies — this is a platform pattern, not a one-off app.
