# apps/web — reviewer console

React + Vite console for the ClaimSight review desk.

## Purpose

HITL UI: claim queue, per-agent findings, citations, subgraph JSON, redacted source, approve / edit / override / escalate. AI ops and audit views.

## Run

```bash
npm install
npm run dev
```

Proxies `/claims`, `/demo`, `/metrics`, `/audit` to `http://localhost:8000`. Override with `VITE_API_BASE`.

Actor is `X-Actor` from the masthead select (`adjuster.front` / `reviewer.senior` / `director.medical`).

## What this is not

Not a production EHR. Not Tailwind/shadcn (see as-built). No live PHI hydration in the default packet (use `?hydrate=true` on the API, audited).
