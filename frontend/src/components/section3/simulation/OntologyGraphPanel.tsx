"use client";

/**
 * 우측 패널 — ontology graph + 통계.
 *
 * target_selected 게이트 도착 시 backend /graph/{sid} 호출하여
 * target method 중심 1-hop graph 표시. 노드 / 엣지 / 통계.
 */
import { useEffect, useState } from "react";
import { Network, Loader2 } from "lucide-react";
import { simulationApi, type GraphResponse } from "@/lib/section3/simulation";

interface Props {
  sessionId: string | null;
  refreshKey: number; // decisions 길이 변화 시 재요청
}

const NODE_COLOR: Record<string, string> = {
  term: "bg-blue-100 border-blue-400 text-blue-800",
  action: "bg-violet-100 border-violet-400 text-violet-800",
  code_method: "bg-emerald-100 border-emerald-400 text-emerald-800",
  code_type: "bg-amber-100 border-amber-400 text-amber-800",
  rule: "bg-rose-100 border-rose-400 text-rose-800",
};

export function OntologyGraphPanel({ sessionId, refreshKey }: Props) {
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) {
      setGraph(null);
      return;
    }
    setLoading(true);
    setError(null);
    simulationApi.graph(sessionId)
      .then(setGraph)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [sessionId, refreshKey]);

  return (
    <>
      <div className="flex items-center gap-2">
        <Network size={14} className="text-emerald-600" />
        <h3 className="text-sm font-semibold text-gray-700">온톨로지 그래프</h3>
        {loading && <Loader2 size={11} className="animate-spin text-gray-400" />}
        {graph && <span className="text-[10px] text-gray-400 ml-auto">{graph.note}</span>}
      </div>

      {!sessionId && (
        <div className="text-xs text-gray-500 border border-dashed border-gray-300 rounded p-4 text-center">
          질문을 보내면 선택된 메서드 중심의<br />호출·용어 관계가 표시됩니다.
        </div>
      )}

      {error && (
        <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2">
          {error}
        </div>
      )}

      {graph && graph.nodes.length === 0 && (
        <div className="text-xs text-gray-500 border border-dashed border-gray-300 rounded p-3">
          {graph.note || "아직 노드가 없습니다 — 후보를 선택해 보세요"}
        </div>
      )}

      {graph && graph.nodes.length > 0 && (
        <>
          <div className="text-[11px] text-gray-600 truncate">
            <strong>중심:</strong>{" "}
            <code className="text-emerald-700">{graph.target_fqn.split(".").pop()}</code>
          </div>
          <_GraphSVG nodes={graph.nodes} edges={graph.edges} centerId={graph.target_fqn} />

          <div className="border-t border-gray-200 pt-2 mt-2 text-[10px] text-gray-500">
            <strong>활용</strong>: 변경 영향은 callers 위로, 구현체는 callees 아래로.
          </div>
        </>
      )}
    </>
  );
}

/** SVG 그래프 — center + 1-hop 원형 배치 + wheel zoom + drag pan. */
function _GraphSVG({ nodes, edges, centerId }: {
  nodes: { id: string; label: string; kind: string }[];
  edges: { source: string; target: string; kind: string }[];
  centerId: string;
}) {
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState<{ x0: number; y0: number; px: number; py: number } | null>(null);

  const W = 360, H = 460, CX = W / 2, CY = H / 2;
  const center = nodes.find((n) => n.id === centerId) ?? nodes[0];
  const others = nodes.filter((n) => n.id !== center.id);
  // 원형 배치
  const positions: Record<string, { x: number; y: number }> = {};
  positions[center.id] = { x: CX, y: CY };
  const R = 100;
  others.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / Math.max(others.length, 1) - Math.PI / 2;
    positions[n.id] = { x: CX + R * Math.cos(angle), y: CY + R * Math.sin(angle) };
  });

  const KIND_FILL: Record<string, string> = {
    term: "#dbeafe", action: "#ede9fe", code_method: "#d1fae5",
    code_type: "#fef3c7", rule: "#fee2e2",
  };
  const KIND_STROKE: Record<string, string> = {
    term: "#3b82f6", action: "#8b5cf6", code_method: "#10b981",
    code_type: "#f59e0b", rule: "#ef4444",
  };

  function onWheel(e: React.WheelEvent<SVGSVGElement>) {
    e.preventDefault();
    const delta = e.deltaY < 0 ? 1.15 : 1 / 1.15;
    setZoom((z) => Math.max(0.4, Math.min(4, z * delta)));
  }
  function onMouseDown(e: React.MouseEvent<SVGSVGElement>) {
    setDragging({ x0: e.clientX, y0: e.clientY, px: pan.x, py: pan.y });
  }
  function onMouseMove(e: React.MouseEvent<SVGSVGElement>) {
    if (!dragging) return;
    setPan({ x: dragging.px + (e.clientX - dragging.x0) / zoom,
             y: dragging.py + (e.clientY - dragging.y0) / zoom });
  }
  function onMouseUp() { setDragging(null); }

  return (
    <div className="relative">
      <div className="absolute top-1 right-1 z-10 flex gap-1 text-[10px]">
        <button onClick={() => setZoom((z) => Math.min(4, z * 1.25))}
          className="bg-white border border-gray-300 rounded w-5 h-5 hover:bg-emerald-50">+</button>
        <button onClick={() => setZoom((z) => Math.max(0.4, z / 1.25))}
          className="bg-white border border-gray-300 rounded w-5 h-5 hover:bg-emerald-50">−</button>
        <button onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}
          className="bg-white border border-gray-300 rounded px-1.5 hover:bg-emerald-50">⌂</button>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H}
        className={"border border-gray-200 rounded bg-slate-50 select-none " + (dragging ? "cursor-grabbing" : "cursor-grab")}
        onWheel={onWheel} onMouseDown={onMouseDown} onMouseMove={onMouseMove} onMouseUp={onMouseUp} onMouseLeave={onMouseUp}>
        <defs>
          <marker id="arr" markerWidth="8" markerHeight="8" refX="7" refY="3.5" orient="auto" markerUnits="strokeWidth">
            <path d="M0,0 L7,3.5 L0,7 Z" fill="#94a3b8" />
          </marker>
        </defs>
        <g transform={`translate(${pan.x * zoom + CX * (1 - zoom)}, ${pan.y * zoom + CY * (1 - zoom)}) scale(${zoom})`}>
          {/* edges */}
          {edges.map((e, i) => {
            const a = positions[e.source]; const b = positions[e.target];
            if (!a || !b) return null;
            return (
              <g key={i}>
                <line x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                  stroke="#94a3b8" strokeWidth="1.5" markerEnd="url(#arr)" />
                <text x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 - 4} fontSize="10" fill="#475569" textAnchor="middle">
                  {e.kind}
                </text>
              </g>
            );
          })}
          {/* nodes */}
          {nodes.map((n) => {
            const p = positions[n.id];
            if (!p) return null;
            const isCenter = n.id === center.id;
            const r = isCenter ? 34 : 28;
            return (
              <g key={n.id}>
                <circle cx={p.x} cy={p.y} r={r}
                  fill={KIND_FILL[n.kind] ?? "#e2e8f0"}
                  stroke={KIND_STROKE[n.kind] ?? "#64748b"}
                  strokeWidth={isCenter ? 3 : 2} />
                <text x={p.x} y={p.y - 1} fontSize="11" textAnchor="middle" fill="#0f172a"
                  fontWeight={isCenter ? "bold" : "600"}>
                  {n.label.length > 11 ? n.label.slice(0, 11) + "…" : n.label}
                </text>
                <text x={p.x} y={p.y + 11} fontSize="9" textAnchor="middle" fill="#475569">
                  {n.kind}
                </text>
              </g>
            );
          })}
        </g>
      </svg>
      <div className="text-[9px] text-gray-400 mt-1">wheel: zoom · drag: pan · ⌂: reset</div>
    </div>
  );
}
