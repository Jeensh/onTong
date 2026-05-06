"use client";

/**
 * ELK PoC spike page (R4-T1.2, 안건 1 C 결정).
 *
 * dagre vs ELK 비교 + compound expand-in-place 검증 + 5K 노드 layout 시간 측정.
 *
 * URL: http://localhost:3000/elk-spike
 *
 * Layout 옵션:
 *   - dagre TB (현재 production)
 *   - ELK Layered (compound 지원)
 *   - ELK Box (compound 우선)
 *   - ELK Force (작은 그래프용)
 *
 * Compound 토글: code_type 노드를 패키지 별 group node 로 nest.
 *
 * 측정: layout 시간 (ms), 노드 수, 엣지 수.
 */
import { useEffect, useMemo, useState } from "react";
import {
  ReactFlow, Background, Controls, MiniMap,
  type Node, type Edge, type NodeProps,
  Handle, Position, MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import dagre from "@dagrejs/dagre";

// elkjs main 이 Node 'web-worker' 의존 — 브라우저에서는 elk-api lazy import
// (혹은 webpack alias). spike 라 dynamic import 가 가장 단순.
type ElkInstance = { layout: (graph: unknown) => Promise<unknown> };
let _elkPromise: Promise<ElkInstance> | null = null;
function getElk(): Promise<ElkInstance> {
  if (!_elkPromise) {
    _elkPromise = import("elkjs/lib/elk-api.js").then((mod) => {
      const Cls = (mod as unknown as { default: new (opts: { workerUrl: string }) => ElkInstance }).default;
      return new Cls({ workerUrl: "/elk-worker.min.js" });
    });
  }
  return _elkPromise;
}
import {
  ontologyApi,
  type GraphEdgeDTO,
  type GraphNodeDTO,
  type OntologyGraphDTO,
} from "@/lib/api/ontology";

const NODE_W = 200;
const NODE_H = 48;
type LayoutName = "dagre-tb" | "elk-layered" | "elk-box" | "elk-force";

const KIND_COLOR = { term: "#a78bfa", code_type: "#fbbf24", action: "#fb923c" };

export default function ElkSpikePage() {
  const [repoId, setRepoId] = useState("slab-design-real");
  const [layout, setLayout] = useState<LayoutName>("elk-layered");
  const [compound, setCompound] = useState(true);
  const [data, setData] = useState<OntologyGraphDTO | null>(null);
  const [loading, setLoading] = useState(false);
  const [layoutMs, setLayoutMs] = useState(0);
  const [fetchMs, setFetchMs] = useState(0);
  const [rfNodes, setRfNodes] = useState<Node[]>([]);
  const [rfEdges, setRfEdges] = useState<Edge[]>([]);
  const [error, setError] = useState<string | null>(null);

  // 데이터 로드 — n_max 600 (full subgraph 비슷하게 가져오기)
  useEffect(() => {
    setLoading(true);
    setError(null);
    const t0 = performance.now();
    ontologyApi
      .getOntologyGraph(repoId, { mode: "neighborhood", n_max: 600 })
      .then((g) => {
        setFetchMs(performance.now() - t0);
        setData(g);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [repoId]);

  // Layout — data / layout / compound 변화 시 재계산
  useEffect(() => {
    if (!data) return;
    let cancelled = false;
    setLayoutMs(0);
    const t0 = performance.now();

    const run = async () => {
      try {
        const { nodes, edges } = data;
        if (layout === "dagre-tb") {
          const out = layoutDagre(nodes, edges, compound);
          if (!cancelled) {
            setRfNodes(out.rfNodes); setRfEdges(out.rfEdges);
            setLayoutMs(performance.now() - t0);
          }
        } else {
          const algo = layout === "elk-layered" ? "layered"
                     : layout === "elk-box"     ? "box"
                     : "force";
          const out = await layoutElk(nodes, edges, algo, compound);
          if (!cancelled) {
            setRfNodes(out.rfNodes); setRfEdges(out.rfEdges);
            setLayoutMs(performance.now() - t0);
          }
        }
      } catch (e) {
        console.error("[elk-spike] layout error:", e);
        if (!cancelled) {
          setError(e instanceof Error ? `Layout 실패: ${e.message}` : String(e));
        }
      }
    };

    void run();
    return () => { cancelled = true; };
  }, [data, layout, compound]);

  return (
    <div className="flex flex-col h-screen bg-slate-950 text-slate-100">
      <header className="px-4 py-2 border-b border-slate-700 bg-slate-900 text-sm flex flex-wrap items-center gap-3">
        <h1 className="font-bold">ELK PoC spike</h1>
        <span className="text-xs text-slate-400">R4-T1.2 — 안건 1 micro-decision 입력</span>

        <span className="ml-4">repo:</span>
        <select value={repoId} onChange={(e) => setRepoId(e.target.value)}
                className="bg-slate-800 border border-slate-700 rounded px-2 py-0.5 text-xs">
          <option value="slab-design-real">slab-design-real (~117 노드)</option>
          <option value="synthetic-5k">synthetic-5k (~5K 노드)</option>
        </select>

        <span className="ml-2">layout:</span>
        <select value={layout} onChange={(e) => setLayout(e.target.value as LayoutName)}
                className="bg-slate-800 border border-slate-700 rounded px-2 py-0.5 text-xs">
          <option value="dagre-tb">dagre TB (현재 production)</option>
          <option value="elk-layered">ELK Layered</option>
          <option value="elk-box">ELK Box</option>
          <option value="elk-force">ELK Force</option>
        </select>

        <label className="ml-2 flex items-center gap-1 text-xs">
          <input type="checkbox" checked={compound} onChange={(e) => setCompound(e.target.checked)} />
          Compound (패키지 group)
        </label>

        <div className="ml-auto text-xs flex gap-3 font-mono">
          <span>fetch <strong className="text-emerald-400">{fetchMs.toFixed(0)}ms</strong></span>
          <span>layout <strong className="text-emerald-400">{layoutMs.toFixed(0)}ms</strong></span>
          <span>nodes <strong className="text-amber-400">{rfNodes.length}</strong></span>
          <span>edges <strong className="text-amber-400">{rfEdges.length}</strong></span>
        </div>
      </header>

      {loading && <div className="p-8 text-center text-slate-400">데이터 로딩...</div>}
      {error && <div className="p-8 text-rose-400">{error}</div>}

      <div className="flex-1 relative">
        <ReactFlow
          key={`${repoId}|${layout}|${compound}|${rfNodes.length}`}
          nodes={rfNodes}
          edges={rfEdges}
          nodeTypes={NODE_TYPES}
          fitView
          fitViewOptions={{ padding: 0.18 }}
          proOptions={{ hideAttribution: true }}
          minZoom={0.05}
          maxZoom={2}
        >
          <Background gap={16} size={1} />
          <Controls position="bottom-left" />
          <MiniMap
            position="bottom-right"
            pannable zoomable
            nodeColor={(n) => {
              const k = (n.data as { kind?: string } | undefined)?.kind;
              return KIND_COLOR[k as keyof typeof KIND_COLOR] ?? "#94a3b8";
            }}
            maskColor="rgba(0,0,0,0.4)"
            className="!bg-slate-900 !border !border-slate-700"
          />
        </ReactFlow>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Layout backends
// ---------------------------------------------------------------------------
function packageOf(n: GraphNodeDTO): string | null {
  if (n.kind !== "code_type") return null;
  return n.domain ?? null;
}

function layoutDagre(
  nodes: GraphNodeDTO[],
  edges: GraphEdgeDTO[],
  compound: boolean,
) {
  // dagre 는 compound 미지원 — flat layout. compound=true 면 패키지 prefix label 만 추가.
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "TB", nodesep: 32, ranksep: 90, marginx: 20, marginy: 20 });
  g.setDefaultEdgeLabel(() => ({}));
  for (const n of nodes) g.setNode(n.id, { width: NODE_W, height: NODE_H });
  for (const e of edges) g.setEdge(e.source, e.target);
  dagre.layout(g);

  const rfNodes: Node[] = nodes.map((n) => {
    const pos = g.node(n.id);
    return {
      id: n.id, type: "ontology",
      position: { x: pos.x - NODE_W / 2, y: pos.y - NODE_H / 2 },
      data: { node: n, kind: n.kind, compound },
      draggable: true,
    };
  });
  const rfEdges = edges.map((e) => mkEdge(e));
  return { rfNodes, rfEdges };
}

async function layoutElk(
  nodes: GraphNodeDTO[],
  edges: GraphEdgeDTO[],
  algorithm: "layered" | "box" | "force",
  compound: boolean,
) {
  // compound: code_type 노드를 패키지 별 group node 로 nest.
  // ELK 에서 group 노드는 width/height 비어두면 children 으로 auto-size.
  type ElkChild = {
    id: string;
    width?: number; height?: number;
    children?: ElkChild[];
    layoutOptions?: Record<string, string>;
  };
  type ElkRoot = {
    id: string;
    layoutOptions: Record<string, string>;
    children: ElkChild[];
    edges: { id: string; sources: string[]; targets: string[] }[];
  };

  let elkChildren: ElkChild[];
  if (compound) {
    const byPkg: Record<string, GraphNodeDTO[]> = {};
    const nonGrouped: GraphNodeDTO[] = [];
    for (const n of nodes) {
      const p = packageOf(n);
      if (p) (byPkg[p] = byPkg[p] || []).push(n);
      else nonGrouped.push(n);
    }
    elkChildren = [
      ...Object.entries(byPkg).map<ElkChild>(([pkg, children]) => ({
        id: `pkg::${pkg}`,
        layoutOptions: {
          "elk.algorithm": algorithm,
          "elk.padding": "[top=24,left=8,bottom=8,right=8]",
        },
        children: children.map((c) => ({ id: c.id, width: NODE_W, height: NODE_H })),
      })),
      ...nonGrouped.map<ElkChild>((n) => ({ id: n.id, width: NODE_W, height: NODE_H })),
    ];
  } else {
    elkChildren = nodes.map((n) => ({ id: n.id, width: NODE_W, height: NODE_H }));
  }

  const root: ElkRoot = {
    id: "root",
    layoutOptions: {
      "elk.algorithm": algorithm,
      "elk.layered.spacing.nodeNodeBetweenLayers": "60",
      "elk.spacing.nodeNode": "32",
      "elk.padding": "[top=12,left=12,bottom=12,right=12]",
      "elk.hierarchyHandling": "INCLUDE_CHILDREN",
    },
    children: elkChildren,
    edges: edges.map((e, i) => ({
      id: `e${i}`, sources: [e.source], targets: [e.target],
    })),
  };

  const elk = await getElk();
  const result = await elk.layout(root);

  type ElkOut = { id: string; x?: number; y?: number; width?: number; height?: number; children?: ElkOut[] };
  const rfNodes: Node[] = [];
  const visit = (n: ElkOut, parentId?: string) => {
    if (n.id === "root") {
      n.children?.forEach((c) => visit(c, undefined));
      return;
    }
    if (n.id.startsWith("pkg::")) {
      // group node — render as box (xyflow group / custom)
      rfNodes.push({
        id: n.id,
        type: "groupBox",
        position: { x: n.x ?? 0, y: n.y ?? 0 },
        data: { label: n.id.replace("pkg::", "") },
        style: { width: n.width, height: n.height, zIndex: -1 },
        draggable: false,
        selectable: false,
      });
      n.children?.forEach((c) => visit(c, n.id));
    } else {
      const dto = nodes.find((nd) => nd.id === n.id);
      if (!dto) return;
      rfNodes.push({
        id: n.id, type: "ontology",
        position: { x: n.x ?? 0, y: n.y ?? 0 },
        data: { node: dto, kind: dto.kind, compound },
        parentId: parentId,
        extent: parentId ? "parent" : undefined,
        draggable: true,
      });
    }
  };
  visit(result as unknown as ElkOut);

  const rfEdges = edges.map((e) => mkEdge(e));
  return { rfNodes, rfEdges };
}

// ---------------------------------------------------------------------------
// Edge / Node components
// ---------------------------------------------------------------------------
function mkEdge(e: GraphEdgeDTO): Edge {
  const color = e.kind === "type_realization_primary" ? "#10b981"
              : e.kind === "type_realization_partial" ? "#f59e0b"
              : e.kind === "realization"              ? "#fb923c"
              : e.kind === "composition"              ? "#a78bfa"
              : "#94a3b8";
  return {
    id: e.id, source: e.source, target: e.target,
    type: "smoothstep",
    style: { stroke: color, strokeWidth: 1.4 },
    markerEnd: { type: MarkerType.ArrowClosed, width: 10, height: 10, color },
    animated: e.kind === "type_realization_partial",
  };
}

function OntologyNode({ data }: NodeProps) {
  const d = data as { node: GraphNodeDTO; kind: string };
  const color = KIND_COLOR[d.kind as keyof typeof KIND_COLOR] ?? "#94a3b8";
  return (
    <div
      className="rounded border bg-slate-800 text-slate-100 px-2 py-1 text-[11px] shadow-sm border-l-[3px] border-slate-700"
      style={{ width: NODE_W, height: NODE_H, borderLeftColor: color }}
    >
      <Handle type="target" position={Position.Top} style={{ background: color }} />
      <div className="font-medium truncate">{d.node.label}</div>
      <div className="text-[9.5px] text-slate-400 truncate">
        {d.node.kind} · {d.node.role ?? ""}
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: color }} />
    </div>
  );
}

function GroupBox({ data }: NodeProps) {
  const d = data as { label: string };
  // 패키지 마지막 segment 만 보여주기
  const short = d.label.split(".").slice(-2).join(".");
  return (
    <div className="border border-dashed border-slate-600 rounded bg-slate-800/30 w-full h-full">
      <div className="text-[10px] text-slate-400 px-1 pt-0.5 font-mono truncate">{short}</div>
    </div>
  );
}

const NODE_TYPES = { ontology: OntologyNode, groupBox: GroupBox };
