# services/graphrag — knowledge graph + hybrid retrieve

## Schema (nodes)

`Patient`, `Provider`, `Claim`, `Diagnosis`, `Procedure`, `PolicyClause`, `Guideline`.

Relationships: `HAS_CLAIM`, `HAS_DIAGNOSIS`, `FOR_PROCEDURE`, `REQUIRES`, `GOVERNED_BY`, `BILLED`.

## Stores

- `MemoryGraphStore` — CI and no-Docker default
- `Neo4jGraphStore` — seed + writes when `NEO4J_URI` is reachable

## Retriever

`HybridRetriever.retrieve` = graph subgraph (including **failed step-therapy history**) + token-Jaccard passages.

`vector_only` deliberately omits prior-claim facts — that is the Phase 2 beat.

## Seed

```bash
python -m claimsight_graphrag.seed
```

## What this is not

Not a real payer graph. Not Neo4j GDS. Not OpenAI embeddings.
