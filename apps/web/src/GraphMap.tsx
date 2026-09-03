type Node = { id: string; label: string; kind: string };

type Props = {
  subgraph: Record<string, any>;
  claimId: string;
};

function short(id: string): string {
  return id.length > 18 ? `${id.slice(0, 16)}…` : id;
}

export default function GraphMap({ subgraph, claimId }: Props) {
  const history: Record<string, any>[] = subgraph.history || [];
  const policies: Record<string, any>[] = subgraph.policies || [];
  const guidelines: Record<string, any>[] = subgraph.guidelines || [];
  const procedures: Record<string, any>[] = subgraph.procedures || [];
  const diagnoses: Record<string, any>[] = subgraph.diagnoses || [];
  const patient = subgraph.patient || {};
  const provider = subgraph.provider || {};

  const nodes: Node[] = [];
  if (patient.id) nodes.push({ id: patient.id, label: patient.id, kind: "patient" });
  if (provider.id) nodes.push({ id: provider.id, label: provider.id, kind: "provider" });
  nodes.push({ id: claimId, label: claimId, kind: "claim" });
  for (const h of history) nodes.push({ id: h.id, label: h.id, kind: "prior" });
  for (const p of procedures) nodes.push({ id: p.id, label: `${p.id} ${p.name || ""}`.trim(), kind: "proc" });
  for (const d of diagnoses) nodes.push({ id: d.id, label: d.id, kind: "dx" });
  for (const p of policies) nodes.push({ id: p.id, label: p.id, kind: "policy" });
  for (const g of guidelines) nodes.push({ id: g.id, label: g.id, kind: "guide" });

  const seen = new Set<string>();
  const uniq = nodes.filter((n) => (seen.has(n.id) ? false : (seen.add(n.id), true)));

  const lanes: Record<string, Node[]> = {
    people: uniq.filter((n) => n.kind === "patient" || n.kind === "provider"),
    claims: uniq.filter((n) => n.kind === "claim" || n.kind === "prior"),
    clinical: uniq.filter((n) => n.kind === "proc" || n.kind === "dx"),
    rules: uniq.filter((n) => n.kind === "policy" || n.kind === "guide"),
  };

  const width = 640;
  const rowH = 72;
  const height = rowH * 4 + 24;
  const pos = new Map<string, { x: number; y: number }>();
  Object.values(lanes).forEach((lane, row) => {
    lane.forEach((n, i) => {
      const gap = width / (lane.length + 1);
      pos.set(n.id, { x: gap * (i + 1), y: 28 + row * rowH });
    });
  });

  const edges: [string, string][] = [];
  if (patient.id) edges.push([patient.id, claimId]);
  if (provider.id) edges.push([provider.id, claimId]);
  for (const h of history) {
    if (patient.id) edges.push([patient.id, h.id]);
    edges.push([h.id, claimId]);
  }
  for (const p of procedures) edges.push([claimId, p.id]);
  for (const d of diagnoses) edges.push([claimId, d.id]);
  for (const p of policies) {
    const proc = procedures[0];
    edges.push([proc?.id || claimId, p.id]);
  }
  for (const g of guidelines) {
    const dx = diagnoses[0];
    edges.push([dx?.id || claimId, g.id]);
  }

  return (
    <div className="graph-map">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Claim subgraph">
        {edges.map(([a, b], i) => {
          const pa = pos.get(a);
          const pb = pos.get(b);
          if (!pa || !pb) return null;
          return (
            <line
              key={`${a}-${b}-${i}`}
              x1={pa.x}
              y1={pa.y}
              x2={pb.x}
              y2={pb.y}
              className="g-edge"
            />
          );
        })}
        {uniq.map((n) => {
          const p = pos.get(n.id);
          if (!p) return null;
          return (
            <g key={n.id} transform={`translate(${p.x},${p.y})`}>
              <rect className={`g-node ${n.kind}`} x={-54} y={-14} width={108} height={28} rx={2} />
              <text textAnchor="middle" y={4}>
                {short(n.label)}
              </text>
            </g>
          );
        })}
      </svg>
      <p className="g-legend">
        <span className="prior">prior claim</span>
        <span className="policy">policy</span>
        <span className="guide">guideline</span>
      </p>
    </div>
  );
}
