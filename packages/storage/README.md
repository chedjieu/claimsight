# packages/storage — S3-compatible object store

`ObjectStore.put_bytes` / `get_bytes`.

- MinIO or AWS S3 when `S3_ACCESS_KEY` is set
- Disk fallback under `./data/docs` otherwise

GCS later: S3-compat endpoint or a thin native adapter — same `ObjectStore` surface.

## What this is not

Not client-side encryption (dev stores plaintext). Not a DAM.
