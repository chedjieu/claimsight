# ClaimSight — compliance checklist (not a certification)

This is the Phase 5 artifact: a **checklist**, not a HIPAA BAA or SOC 2 report. Do not use real PHI.

## In this repo

- [x] De-identify before any model-shaped prompt (`PhiGuard`)
- [x] Re-identification vault is Fernet-sealed at rest; hydrate is medical-director + audited
- [x] Documents written to disk/MinIO are sealed before put
- [x] Prompt-injection scan on source documents
- [x] Compliance node scans outbound packets for leaked identifiers
- [x] Append-only audit log (ingest, orchestrate, decide, hydrate, purge)
- [x] Demo RBAC tiers (front-line / senior / director)
- [x] Right-to-delete purge (claim notes, vault map, objects, graph claim + decision nodes)
- [x] TLS is the compose/cloud ingress concern; local demo is HTTP
- [x] Vendor BAA is a hard gate before any real PHI or production model account

## Later (not claimed here)

- [ ] OIDC SSO (Auth0 / Keycloak / cloud IAM)
- [ ] Cloud KMS-managed vault keys
- [ ] Column-level encryption via Cloud SQL / RDS
- [ ] Signed BAA with each model and storage vendor
- [ ] Production network isolation, VPC-SC / PrivateLink
- [ ] Formal HIPAA risk analysis and SOC 2 Type II
