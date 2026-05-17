"use client";

/**
 * 간단 SVG 기반 ontology 그래프 — modeling.ontology_trace.nodes/edges 직접 시각화.
 * 외부 lib 없이 빠르게 force-free layout (그룹별 column).
 */

interface OntologyNode {
  id: string;
  label: string;
  group: string;
}

interface OntologyEdge {
  from: string;
  to: string;
  label?: string;
}

interface Props {
  nodes: OntologyNode[];
  edges: OntologyEdge[];
  cypher?: string;
  height?: number;
}

const GROUP_TONE: Record<string, { fill: string; stroke: string; text: string }> = {
  term: { fill: "#fce7f3", stroke: "#db2777", text: "#831843" },
  step: { fill: "#dbeafe", stroke: "#2563eb", text: "#1e3a8a" },
  method: { fill: "#d1fae5", stroke: "#059669", text: "#064e3b" },
  class: { fill: "#cffafe", stroke: "#0891b2", text: "#164e63" },
  table: { fill: "#fed7aa", stroke: "#ea580c", text: "#7c2d12" },
  standard: { fill: "#fef3c7", stroke: "#d97706", text: "#78350f" },
  variable: { fill: "#e9d5ff", stroke: "#9333ea", text: "#581c87" },
  default: { fill: "#e5e7eb", stroke: "#6b7280", text: "#1f2937" },
};

const GROUP_ORDER = ["term", "standard", "variable", "step", "class", "method", "table"];

export function OntologyGraphSVG({ nodes, edges, cypher, height = 420 }: Props) {
  if (!nodes?.length) {
    return <div className="text-xs text-muted-foreground">시각화할 ontology 노드 없음.</div>;
  }

  // 그룹별 column 배치
  const groupedByCol: Record<string, OntologyNode[]> = {};
  for (const n of nodes) {
    const g = n.group || "default";
    if (!groupedByCol[g]) groupedByCol[g] = [];
    groupedByCol[g].push(n);
  }
  const orderedGroups = [...GROUP_ORDER.filter((g) => groupedByCol[g]?.length), ...Object.keys(groupedByCol).filter((g) => !GROUP_ORDER.includes(g))];

  const colWidth = 200;
  const rowHeight = 60;
  const padding = 30;
  const totalWidth = orderedGroups.length * colWidth + padding * 2;
  const maxRows = Math.max(1, ...orderedGroups.map((g) => groupedByCol[g].length));
  const totalHeight = Math.max(height, maxRows * rowHeight + padding * 2 + 40);

  const positions = new Map<string, { x: number; y: number; node: OntologyNode }>();
  orderedGroups.forEach((g, colIdx) => {
    const groupNodes = groupedByCol[g];
    groupNodes.forEach((n, rowIdx) => {
      positions.set(n.id, {
        x: padding + colIdx * colWidth + colWidth / 2,
        y: padding + 30 + rowIdx * rowHeight,
        node: n,
      });
    });
  });

  return (
    <div className="space-y-2">
      <div className="border border-border rounded-lg bg-background overflow-auto" style={{ maxHeight: height + 40 }}>
        <svg width={totalWidth} height={totalHeight}>
          <defs>
            <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#9ca3af" />
            </marker>
          </defs>

          {/* group headers */}
          {orderedGroups.map((g, colIdx) => (
            <text
              key={`hdr-${g}`}
              x={padding + colIdx * colWidth + colWidth / 2}
              y={padding}
              textAnchor="middle"
              fontSize="11"
              fontWeight="600"
              fill="#6b7280"
              style={{ textTransform: "uppercase", letterSpacing: "0.08em" }}
            >
              {g}
            </text>
          ))}

          {/* edges */}
          {edges?.map((e, i) => {
            const a = positions.get(e.from);
            const b = positions.get(e.to);
            if (!a || !b) return null;
            const midX = (a.x + b.x) / 2;
            const midY = (a.y + b.y) / 2;
            return (
              <g key={`e-${i}`}>
                <line
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke="#cbd5e1"
                  strokeWidth={1.2}
                  markerEnd="url(#arr)"
                />
                {e.label && (
                  <text x={midX} y={midY - 4} textAnchor="middle" fontSize="9" fill="#94a3b8" style={{ pointerEvents: "none" }}>
                    {e.label}
                  </text>
                )}
              </g>
            );
          })}

          {/* nodes */}
          {Array.from(positions.values()).map(({ x, y, node }) => {
            const tone = GROUP_TONE[node.group] || GROUP_TONE.default;
            const lines = node.label.split("\n").slice(0, 2);
            return (
              <g key={node.id}>
                <rect
                  x={x - 80}
                  y={y - 18}
                  width={160}
                  height={36}
                  rx={8}
                  fill={tone.fill}
                  stroke={tone.stroke}
                  strokeWidth={1.5}
                />
                <text x={x} y={y + 2} textAnchor="middle" fontSize="10" fontWeight="600" fill={tone.text}>
                  {lines[0]?.slice(0, 22)}
                </text>
                {lines[1] && (
                  <text x={x} y={y + 13} textAnchor="middle" fontSize="9" fill={tone.text} opacity={0.8}>
                    {lines[1].slice(0, 24)}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>

      {cypher && (
        <details className="text-[10px]">
          <summary className="cursor-pointer text-muted-foreground hover:text-foreground">▶ Cypher (modeling 이 실행)</summary>
          <pre className="mt-1 bg-slate-900 text-slate-100 rounded p-2 overflow-x-auto text-[10px] whitespace-pre-wrap">{cypher}</pre>
        </details>
      )}
    </div>
  );
}
