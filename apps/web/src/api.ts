const base = import.meta.env.VITE_API_BASE || "";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${base}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Actor": localStorage.getItem("claimsight-actor") || "adjuster.front",
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => req<Record<string, unknown>>("/health"),
  claims: () => req<ClaimRow[]>("/claims"),
  claim: (id: string, hydrate = false) =>
    req<ClaimDetail>(`/claims/${id}${hydrate ? "?hydrate=true" : ""}`),
  decide: (id: string, body: DecideBody) =>
    req<Record<string, unknown>>(`/claims/${id}/decide`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  purge: (id: string) =>
    req<Record<string, unknown>>(`/claims/${id}`, { method: "DELETE" }),
  audit: () => req<AuditRow[]>("/audit?limit=80"),
  metrics: () => req<Metrics>("/metrics"),
  demo: (name: string) => req<{ claim_id: string }>(`/demo/${name}`, { method: "POST" }),
};

export type Permissions = {
  decide: boolean;
  approve: boolean;
  override: boolean;
  escalate: boolean;
  hydrate: boolean;
  purge: boolean;
};

export type ClaimRow = {
  id: string;
  patient_id: string;
  provider_id: string;
  icd10: string[];
  cpt: string[];
  amount_usd: number;
  service_date: string;
  status: string;
  recommendation: string | null;
  confidence: number;
  route: string | null;
  qa_sampled?: boolean;
  specialty?: string | null;
  permissions?: Permissions;
  ingested_at: string | null;
};

export type ClaimDetail = ClaimRow & {
  packet: Record<string, unknown>;
  model_name: string;
  prompt_version: string;
  decided_by: string | null;
  token_used: number;
};

export type DecideBody = {
  action: "approve" | "edit_approve" | "override_deny" | "escalate";
  reason?: string;
  edited_narrative?: string;
};

export type AuditRow = {
  id: number;
  ts: string | null;
  actor: string;
  action: string;
  entity_id: string;
  reason: string | null;
};

export type Metrics = {
  claim_count: number;
  status_counts: Record<string, number>;
  override_rate: number;
  override_rate_by_cpt: Record<string, number>;
  confidence_histogram: Record<string, number>;
  qa_sampled: number;
  mean_confidence: number;
  mean_tokens: number;
  decided: number;
  queue_depth: number;
  graph: string;
  llm: string;
};
