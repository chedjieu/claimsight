import { useEffect, useState } from "react";
import { api, type AuditRow, type ClaimDetail, type ClaimRow, type Metrics } from "./api";

type View = "queue" | "audit" | "ops";

function money(n: number): string {
  return `$${Math.round(n).toLocaleString("en-US")}`;
}

function statusTone(status: string): string {
  if (["approved"].includes(status)) return "ok";
  if (["denied"].includes(status)) return "hot";
  if (["pending_human_review", "escalated"].includes(status)) return "warn";
  if (status === "ready_for_confirmation") return "ok";
  return "";
}

export default function App() {
  const [view, setView] = useState<View>("queue");
  const [rows, setRows] = useState<ClaimRow[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<ClaimDetail | null>(null);
  const [cite, setCite] = useState<Record<string, unknown> | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [actor, setActor] = useState(localStorage.getItem("claimsight-actor") || "adjuster.front");
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [audit, setAudit] = useState<AuditRow[]>([]);

  async function refresh() {
    const list = await api.claims();
    setRows(list);
    if (!selected && list[0]) setSelected(list[0].id);
  }

  useEffect(() => {
    localStorage.setItem("claimsight-actor", actor);
  }, [actor]);

  useEffect(() => {
    refresh().catch((e) => setErr(String(e)));
  }, []);

  useEffect(() => {
    if (!selected) {
      setDetail(null);
      return;
    }
    api
      .claim(selected)
      .then((d) => {
        setDetail(d);
        const citations = (d.packet.citations as Record<string, unknown>[]) || [];
        setCite(citations[0] || null);
      })
      .catch((e) => setErr(String(e)));
  }, [selected]);

  useEffect(() => {
    if (view === "ops") api.metrics().then(setMetrics).catch((e) => setErr(String(e)));
    if (view === "audit") api.audit().then(setAudit).catch((e) => setErr(String(e)));
  }, [view]);

  const packet = (detail?.packet || {}) as Record<string, any>;
  const findings: Record<string, any>[] = packet.findings || [];
  const citations: Record<string, unknown>[] = packet.citations || [];
  const subgraph = (packet.subgraph || {}) as Record<string, any>;

  async function fire(name: string) {
    setBusy(true);
    setErr("");
    try {
      const res = await api.demo(name);
      await refresh();
      setSelected(res.claim_id);
      setView("queue");
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function decide(action: "approve" | "edit_approve" | "override_deny" | "escalate") {
    if (!detail) return;
    setBusy(true);
    setErr("");
    try {
      await api.decide(detail.id, { action, reason: reason || undefined });
      setReason("");
      const d = await api.claim(detail.id);
      setDetail(d);
      await refresh();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app">
      <header className="mast">
        <div className="wordmark">
          <strong>ClaimSight</strong>
          <span>AI drafts · humans decide</span>
        </div>
        <nav className="nav">
          <button className={view === "queue" ? "on" : ""} onClick={() => setView("queue")}>
            Review desk
          </button>
          <button className={view === "audit" ? "on" : ""} onClick={() => setView("audit")}>
            Audit
          </button>
          <button className={view === "ops" ? "on" : ""} onClick={() => setView("ops")}>
            AI ops
          </button>
        </nav>
        <div className="mast-tools">
          <select value={actor} onChange={(e) => setActor(e.target.value)}>
            <option value="adjuster.front">Front-line reviewer</option>
            <option value="reviewer.senior">Senior clinical</option>
            <option value="director.medical">Medical director</option>
          </select>
          <button disabled={busy} onClick={() => fire("step_therapy")}>
            Step-therapy demo
          </button>
          <button disabled={busy} onClick={() => fire("knee")}>
            Knee demo
          </button>
          <button disabled={busy} className="danger" onClick={() => fire("fraud")}>
            Fraud demo
          </button>
        </div>
      </header>

      {err && <div className="banner">{err}</div>}

      {view === "queue" && (
        <div className="desk">
          <aside className="queue">
            <h2>Queue</h2>
            {rows.length === 0 && <p className="muted">No claims. Fire a demo to seed the desk.</p>}
            {rows.map((r) => (
              <button
                key={r.id}
                className={`qrow ${selected === r.id ? "sel" : ""} ${statusTone(r.status)}`}
                onClick={() => setSelected(r.id)}
              >
                <span className="qid">{r.id}</span>
                <span className="qmeta">
                  {r.cpt.join(", ")} · {money(r.amount_usd)}
                </span>
                <span className="qstat">{r.status.replaceAll("_", " ")}</span>
              </button>
            ))}
          </aside>

          <main className="dossier">
            {!detail && <p className="muted">Select a claim.</p>}
            {detail && (
              <>
                <div className="headline">
                  <div>
                    <h1>{detail.id}</h1>
                    <p className="lede">
                      {detail.patient_id} · {detail.provider_id} · ICD {detail.icd10.join(", ")} · CPT{" "}
                      {detail.cpt.join(", ")}
                    </p>
                  </div>
                  <div className="rec">
                    <em>{detail.recommendation || "—"}</em>
                    <span>{Math.round((detail.confidence || 0) * 100)}% confidence</span>
                    <small>{detail.route?.replaceAll("_", " ")}</small>
                  </div>
                </div>

                <p className="rationale">{packet.rationale || "Pipeline has not finished."}</p>

                <section>
                  <h3>Specialist findings</h3>
                  <div className="findings">
                    {findings.map((f) => (
                      <article key={f.agent}>
                        <header>
                          <strong>{f.agent}</strong>
                          <span className={`pill ${f.verdict}`}>{f.verdict}</span>
                        </header>
                        <p>{f.narrative}</p>
                        <code>{(f.flags || []).join(" · ") || "no flags"}</code>
                      </article>
                    ))}
                  </div>
                </section>

                <section className="split">
                  <div>
                    <h3>Citations</h3>
                    <ul className="cites">
                      {citations.map((c) => (
                        <li key={String(c.id)}>
                          <button onClick={() => setCite(c)}>
                            <strong>{String(c.id)}</strong>
                            <span>
                              {String(c.kind)} · {String(c.source)}
                            </span>
                          </button>
                        </li>
                      ))}
                    </ul>
                    {cite && (
                      <blockquote>
                        <strong>{String(cite.id)}</strong>
                        <p>{String(cite.text)}</p>
                      </blockquote>
                    )}
                  </div>
                  <div>
                    <h3>Graph subgraph</h3>
                    <pre className="graph">
                      {JSON.stringify(
                        {
                          history: (subgraph.history || []).map((h: any) => ({
                            id: h.id,
                            cpt: h.cpt,
                            outcome: h.outcome,
                            date: h.service_date,
                          })),
                          failed_steps: subgraph.failed_steps,
                          policies: (subgraph.policies || []).map((p: any) => p.id),
                          guidelines: (subgraph.guidelines || []).map((g: any) => g.id),
                          provider: subgraph.provider_stats,
                        },
                        null,
                        2,
                      )}
                    </pre>
                    <h3>Redacted source</h3>
                    <pre className="graph">{String(packet.redacted_notes || "—")}</pre>
                  </div>
                </section>

                {["ready_for_confirmation", "pending_human_review"].includes(detail.status) && (
                  <section className="hitl">
                    <h3>Human decision</h3>
                    <textarea
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      placeholder="Reason / clinical note (captured as labeled feedback)"
                    />
                    <div className="actions">
                      <button disabled={busy} onClick={() => decide("approve")}>
                        Approve
                      </button>
                      <button disabled={busy} onClick={() => decide("edit_approve")}>
                        Edit &amp; approve
                      </button>
                      <button disabled={busy} className="danger" onClick={() => decide("override_deny")}>
                        Override deny
                      </button>
                      <button disabled={busy} onClick={() => decide("escalate")}>
                        Escalate
                      </button>
                    </div>
                  </section>
                )}
              </>
            )}
          </main>
        </div>
      )}

      {view === "audit" && (
        <div className="plain">
          <h2>Append-only audit</h2>
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>Actor</th>
                <th>Action</th>
                <th>Claim</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {audit.map((a) => (
                <tr key={a.id}>
                  <td>{a.ts}</td>
                  <td>{a.actor}</td>
                  <td>{a.action}</td>
                  <td>{a.entity_id}</td>
                  <td>{a.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {view === "ops" && metrics && (
        <div className="plain ops">
          <h2>AI ops</h2>
          <dl>
            <div>
              <dt>Claims</dt>
              <dd>{metrics.claim_count}</dd>
            </div>
            <div>
              <dt>Queue depth</dt>
              <dd>{metrics.queue_depth}</dd>
            </div>
            <div>
              <dt>Override rate</dt>
              <dd>{Math.round(metrics.override_rate * 100)}%</dd>
            </div>
            <div>
              <dt>Mean confidence</dt>
              <dd>{metrics.mean_confidence}</dd>
            </div>
            <div>
              <dt>Mean tokens</dt>
              <dd>{metrics.mean_tokens}</dd>
            </div>
            <div>
              <dt>Graph / LLM</dt>
              <dd>
                {metrics.graph} · {metrics.llm}
              </dd>
            </div>
          </dl>
          <pre>{JSON.stringify(metrics.status_counts, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
