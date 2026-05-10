"use client";

import { useEffect, useRef, useState } from "react";

export interface SubgraphNode {
  id: string;
  label: string;
  group: string; // term | step | standard | method | class | table | order | …
}

export interface SubgraphEdge {
  from: string;
  to: string;
  label?: string;
}

interface Props {
  nodes: SubgraphNode[];
  edges: SubgraphEdge[];
  /** 진하게 그릴 노드 id 집합 (변경 대상, seed 등). */
  highlightIds?: Set<string>;
  /** 진하게 그릴 path edge 집합 ("from→to" 키). */
  pathEdgeKeys?: Set<string>;
  /** 노드 클릭 콜백. */
  onNodeClick?: (nodeId: string) => void;
  /** 캔버스 높이. */
  height?: number;
  /** 빈 상태 메시지. */
  emptyMessage?: string;
}

const GROUP_COLORS: Record<string, string> = {
  term: "#f59e0b",       // amber
  step: "#a855f7",       // purple
  standard: "#10b981",   // emerald
  method: "#3b82f6",     // blue
  class: "#6366f1",      // indigo
  table: "#06b6d4",      // cyan
  order: "#ef4444",      // red — 변경 대상 강조
  variable: "#84cc16",   // lime
  errorcode: "#dc2626",  // red 진함
};

interface NodeState {
  id: string;
  label: string;
  group: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
}

/**
 * Force-directed 그래프 시각화 — 외부 라이브러리 없이 SVG + requestAnimationFrame.
 *
 * Coulomb 반발 + Spring 연결 + 중앙 인력으로 자연스럽게 펼쳐진다.
 */
export function OntologySubgraphView({
  nodes,
  edges,
  highlightIds,
  pathEdgeKeys,
  onNodeClick,
  height = 480,
  emptyMessage = "그래프 데이터 없음",
}: Props) {
  const [tick, setTick] = useState(0);
  const [hoverId, setHoverId] = useState<string | null>(null);
  const stateRef = useRef<NodeState[]>([]);
  const adjRef = useRef<Map<string, Set<string>>>(new Map());
  const rafRef = useRef<number | null>(null);

  const width = 800;

  // 노드/엣지가 바뀔 때마다 시뮬레이션 초기화
  useEffect(() => {
    if (nodes.length === 0) {
      stateRef.current = [];
      return;
    }

    // 그룹별로 초기 위치를 살짝 분리해 빠르게 안정화
    const groupAngles = new Map<string, number>();
    const groups = Array.from(new Set(nodes.map((n) => n.group)));
    groups.forEach((g, i) => {
      groupAngles.set(g, (i / groups.length) * Math.PI * 2);
    });

    stateRef.current = nodes.map((n, i) => {
      const baseAngle = groupAngles.get(n.group) ?? 0;
      const jitter = (i / nodes.length) * Math.PI * 2;
      const r = 120 + (i % 3) * 40;
      return {
        id: n.id,
        label: n.label,
        group: n.group,
        x: width / 2 + Math.cos(baseAngle + jitter * 0.3) * r,
        y: height / 2 + Math.sin(baseAngle + jitter * 0.3) * r,
        vx: 0,
        vy: 0,
      };
    });

    // adjacency
    const adj = new Map<string, Set<string>>();
    for (const n of nodes) adj.set(n.id, new Set());
    for (const e of edges) {
      adj.get(e.from)?.add(e.to);
      adj.get(e.to)?.add(e.from);
    }
    adjRef.current = adj;

    // 시뮬레이션 시작
    let frame = 0;
    const animate = () => {
      step();
      setTick((t) => t + 1);
      frame++;
      // ~200 프레임 후 중단 (안정화)
      if (frame < 220) {
        rafRef.current = requestAnimationFrame(animate);
      }
    };
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = requestAnimationFrame(animate);

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes, edges, height]);

  /** 한 step 시뮬레이션. */
  const step = () => {
    const ns = stateRef.current;
    const adj = adjRef.current;
    if (ns.length === 0) return;

    const REPULSION = 5500;
    const SPRING_LEN = 110;
    const SPRING_K = 0.04;
    const DAMPING = 0.78;
    const CENTER_PULL = 0.005;

    // 1. Coulomb 반발
    for (let i = 0; i < ns.length; i++) {
      for (let j = i + 1; j < ns.length; j++) {
        const a = ns[i];
        const b = ns[j];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const dist2 = Math.max(dx * dx + dy * dy, 1);
        const dist = Math.sqrt(dist2);
        const force = REPULSION / dist2;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        a.vx -= fx;
        a.vy -= fy;
        b.vx += fx;
        b.vy += fy;
      }
    }

    // 2. Spring (연결된 쌍)
    for (const e of edges) {
      const a = ns.find((n) => n.id === e.from);
      const b = ns.find((n) => n.id === e.to);
      if (!a || !b) continue;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const force = (dist - SPRING_LEN) * SPRING_K;
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      a.vx += fx;
      a.vy += fy;
      b.vx -= fx;
      b.vy -= fy;
    }

    // 3. Center pull + Velocity 업데이트 + Damping
    for (const n of ns) {
      n.vx += (width / 2 - n.x) * CENTER_PULL;
      n.vy += (height / 2 - n.y) * CENTER_PULL;
      n.vx *= DAMPING;
      n.vy *= DAMPING;
      n.x += n.vx;
      n.y += n.vy;
      // 화면 경계
      n.x = Math.max(40, Math.min(width - 40, n.x));
      n.y = Math.max(30, Math.min(height - 30, n.y));
    }

    // adjRef 사용 안 했지만 향후 hover-relayout 등에 활용 예정 (suppress unused)
    void adj;
  };

  if (nodes.length === 0) {
    return (
      <div
        className="flex items-center justify-center rounded border border-dashed border-gray-300 bg-gray-50 text-sm text-gray-500"
        style={{ height }}
      >
        {emptyMessage}
      </div>
    );
  }

  // tick 의존: 매 시뮬레이션 step마다 재렌더
  void tick;

  return (
    <div className="rounded border border-gray-200 bg-gradient-to-br from-slate-50 to-white shadow-sm">
      <div className="flex items-center justify-between border-b border-gray-100 px-3 py-2">
        <div className="text-xs font-semibold text-gray-700">
          🌐 온톨로지 Subgraph · {nodes.length} 노드 / {edges.length} 관계
        </div>
        <Legend />
      </div>
      <svg
        width="100%"
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        style={{ display: "block" }}
      >
        {/* edges */}
        {edges.map((e, i) => {
          const a = stateRef.current.find((n) => n.id === e.from);
          const b = stateRef.current.find((n) => n.id === e.to);
          if (!a || !b) return null;
          const key = `${e.from}->${e.to}`;
          const onPath = pathEdgeKeys?.has(key);
          const dim = pathEdgeKeys && !onPath;
          return (
            <g key={i}>
              <line
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                stroke={onPath ? "#a855f7" : dim ? "#e5e7eb" : "#cbd5e1"}
                strokeWidth={onPath ? 2.5 : 1}
                strokeDasharray={onPath ? "0" : "0"}
                opacity={dim ? 0.4 : 1}
              />
              {hoverId && (e.from === hoverId || e.to === hoverId) && e.label && (
                <text
                  x={(a.x + b.x) / 2}
                  y={(a.y + b.y) / 2 - 2}
                  textAnchor="middle"
                  fontSize="9"
                  fill="#475569"
                  className="pointer-events-none"
                >
                  {e.label}
                </text>
              )}
            </g>
          );
        })}

        {/* nodes */}
        {stateRef.current.map((n) => {
          const isHL = highlightIds?.has(n.id);
          const onPath =
            pathEdgeKeys &&
            (Array.from(pathEdgeKeys).some(
              (k) => k.startsWith(`${n.id}->`) || k.endsWith(`->${n.id}`)
            ));
          const dim = pathEdgeKeys && !onPath && !isHL;
          const color = GROUP_COLORS[n.group] ?? "#94a3b8";
          const radius = isHL ? 14 : 10;
          const lines = n.label.split("\n");

          return (
            <g
              key={n.id}
              onMouseEnter={() => setHoverId(n.id)}
              onMouseLeave={() => setHoverId(null)}
              onClick={() => onNodeClick?.(n.id)}
              style={{ cursor: onNodeClick ? "pointer" : "default" }}
              opacity={dim ? 0.35 : 1}
            >
              <circle
                cx={n.x}
                cy={n.y}
                r={radius}
                fill={isHL ? color : "white"}
                stroke={color}
                strokeWidth={isHL ? 3 : 2}
              />
              <text
                x={n.x}
                y={n.y + radius + 12}
                textAnchor="middle"
                fontSize={isHL ? "11" : "10"}
                fontWeight={isHL ? 700 : 500}
                fill="#0f172a"
                className="pointer-events-none"
              >
                {lines[0].length > 22 ? lines[0].slice(0, 21) + "…" : lines[0]}
              </text>
              {lines[1] && (
                <text
                  x={n.x}
                  y={n.y + radius + 23}
                  textAnchor="middle"
                  fontSize="9"
                  fill="#64748b"
                  className="pointer-events-none"
                >
                  {lines[1].length > 22 ? lines[1].slice(0, 21) + "…" : lines[1]}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function Legend() {
  const items = [
    { k: "term", label: "Term" },
    { k: "step", label: "Step" },
    { k: "standard", label: "SC" },
    { k: "method", label: "Method" },
    { k: "class", label: "Class" },
    { k: "table", label: "Table" },
    { k: "order", label: "Order" },
  ];
  return (
    <div className="flex flex-wrap gap-1.5 text-[9px]">
      {items.map((it) => (
        <div key={it.k} className="flex items-center gap-0.5">
          <span
            className="inline-block h-2 w-2 rounded-full"
            style={{ backgroundColor: GROUP_COLORS[it.k] }}
          />
          <span className="text-gray-600">{it.label}</span>
        </div>
      ))}
    </div>
  );
}
