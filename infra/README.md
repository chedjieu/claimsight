# infra — local Compose and later clouds

## Compose (canonical)

[compose/docker-compose.yml](compose/docker-compose.yml) — Postgres+pgvector, Neo4j, Redis, MinIO, API, worker, web.

From repo root: `docker compose up --build` (wrapper at `/docker-compose.yml`).

| Service | Port |
|---|---|
| API | 8000 |
| Web | 5173 |
| Postgres | 5432 |
| Neo4j | 7474 / 7687 |
| Redis | 6379 |
| MinIO | 9000 / 9001 |

## Kubernetes stubs

[k8s/](k8s/) — API/web deployments + adapter ConfigMap. Not a production cluster.

## Terraform (Phase 7, not applied)

- [terraform/gcp](terraform/gcp) — Cloud Run, Cloud SQL, Memorystore, GCS
- [terraform/aws](terraform/aws) — ECS cluster, RDS, ElastiCache, S3

Same Python adapters. Do not rewrite agents.

Observability notes: [OBSERVABILITY.md](OBSERVABILITY.md).

## What this is not

Not a live multi-region deployment. Not HIPAA-hardened networking.
