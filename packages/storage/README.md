# packages/storage — S3-compatible object store

`ObjectStore.put_bytes` / `get_bytes` / `delete_prefix`.

- MinIO or AWS S3 when `S3_ACCESS_KEY` is set
- Disk fallback under `./data/docs` otherwise
- Bodies are Fernet-sealed (`CLAIMSIGHT_VAULT_KEY`) before write

GCS later: S3-compat endpoint or a thin native adapter — same `ObjectStore` surface.

## What this is not

Not cloud KMS. Not a DAM.
