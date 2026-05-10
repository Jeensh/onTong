"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  type NodeProps,
  Handle,
  Position,
  type EdgeMarkerType,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Loader2, Search, X, Target, Network, GitFork, Boxes, Link2, Check } from "lucide-react";

// ELK dynamic import (R4-T1.3 안건 1 micro-decision = B 풀 마이그). Next 가 main entry
// 의 'web-worker' 의존을 직접 못 import → web worker 로 lazy load. public/elk-worker.min.js.
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
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  ontologyApi,
  type GraphEdgeDTO,
  type GraphNodeDTO,
  type GraphNodeKind,
  type OntologyGraphDTO,
} from "@/lib/api/ontology";
import { NodePreviewPanel } from "./NodePreviewPanel";
import { PerspectiveDropdown } from "./PerspectiveDropdown";

const NODE_W = 200;
const NODE_H = 48;

/**
 * 실제 import 데이터 기반 ontology graph (P3-5 + R4-T1.3).
 * 노드: BusinessTerm + CodeType + Action
 * 엣지: Inheritance / Composition / TypeRealization / Realization
 * Layout: ELK Layered (R4 micro-decision B = 풀 마이그). 5K cap 600 까지 sub-100ms.
 *         compound (Domain box expand-in-place) 는 안건 4 의 R4-T3.3 에서 활성.
 */
import { useWorkbench, type GraphViewMode } from "./store";

export function OntologyGraph({ repoId }: { repoId: string }) {
  // R4-T2.3 — graph state 가 store 로 이동 (URL sync 가능). UI input 만 local.
  const mode = useWorkbench((s) => s.graphMode);
  const focus = useWorkbench((s) => s.graphFocus);
  const target = useWorkbench((s) => s.graphTarget);
  const nMax = useWorkbench((s) => s.graphNMax);
  const compound = useWorkbench((s) => s.graphCompound);
  const setMode = useWorkbench((s) => s.setGraphViewMode);
  const setFocus = useWorkbench((s) => s.setGraphFocus);
  const setTarget = useWorkbench((s) => s.setGraphTarget);
  const setNMax = useWorkbench((s) => s.setGraphNMax);
  const setCompound = useWorkbench((s) => s.setGraphCompound);

  const [data, setData] = useState<OntologyGraphDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [searchQ, setSearchQ] = useState("");
  const [searchTargetQ, setSearchTargetQ] = useState("");
  // R4-T2.1 — bottom preview panel
  const [previewNode, setPreviewNode] = useState<GraphNodeDTO | null>(null);
  const [pinned, setPinned] = useState(false);
  // P3 폴리싱: hover 시 floating tooltip — click 전 빠른 미리보기.
  const [hoverNode, setHoverNode] = useState<{
    node: GraphNodeDTO;
    x: number;
    y: number;
  } | null>(null);
  const [reloadTick, setReloadTick] = useState(0);   // 큐 mutation 후 그래프 reload

  // 데이터 로드
  useEffect(() => {
    let cancelled = false;
    // path mode 는 focus + target 둘 다 있어야 backend 가 정상 응답 (400 방지)
    if (mode === "path" && (!focus || !target)) {
      setData(null);
      setErr(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setErr(null);
    const opts: Parameters<typeof ontologyApi.getOntologyGraph>[1] = { mode, n_max: nMax };
    if (focus) opts.focus_fqn = focus;
    if (mode === "path" && target) opts.target_fqn = target;
    ontologyApi.getOntologyGraph(repoId, opts)
      .then((g) => {
        if (cancelled) return;
        setData(g);
        // neighborhood mode + focus 없을 때만 자동 focus
        if (mode === "neighborhood" && !focus && g.nodes.length > 30) {
          const deg: Record<string, number> = {};
          for (const e of g.edges) {
            deg[e.source] = (deg[e.source] ?? 0) + 1;
            deg[e.target] = (deg[e.target] ?? 0) + 1;
          }
          const ranked = g.nodes
            .filter((n) => n.kind === "term" || n.kind === "action")
            .map((n) => ({ id: n.id, d: deg[n.id] ?? 0 }))
            .sort((a, b) => b.d - a.d);
          if (ranked[0] && ranked[0].d > 0) setFocus(ranked[0].id);
        }
      })
      .catch((e) => {
        if (cancelled) return;
        setErr(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [repoId, mode, focus, target, nMax, reloadTick]);

  // ELK layout (async). data 변화 시 재계산.
  const [rfNodes, setRfNodes] = useState<Node[]>([]);
  const [rfEdges, setRfEdges] = useState<Edge[]>([]);
  const [layoutBusy, setLayoutBusy] = useState(false);
  useEffect(() => {
    let cancelled = false;
    if (!data || data.nodes.length === 0) {
      setRfNodes([]); setRfEdges([]);
      return;
    }
    setLayoutBusy(true);
    void buildLayout(data.nodes, data.edges, compound).then((out) => {
      if (cancelled) return;
      setRfNodes(out.rfNodes);
      setRfEdges(out.rfEdges);
      setLayoutBusy(false);
    }).catch((e) => {
      if (!cancelled) {
        console.error("[OntologyGraph] ELK layout error", e);
        setLayoutBusy(false);
      }
    });
    return () => { cancelled = true; };
  }, [data, compound]);

  // 검색 매치 (focus + target 공용)
  const searchHits = useMemo(() => {
    if (!searchQ.trim() || !data) return [];
    const q = searchQ.trim().toLowerCase();
    return data.nodes
      .filter((n) => n.label.toLowerCase().includes(q) || n.id.toLowerCase().includes(q))
      .slice(0, 20);
  }, [searchQ, data]);
  const targetHits = useMemo(() => {
    if (!searchTargetQ.trim() || !data) return [];
    const q = searchTargetQ.trim().toLowerCase();
    return data.nodes
      .filter((n) => n.label.toLowerCase().includes(q) || n.id.toLowerCase().includes(q))
      .slice(0, 20);
  }, [searchTargetQ, data]);

  const onNodeClick = useCallback((_e: React.MouseEvent, node: Node) => {
    if (mode === "path") {
      // path mode: 첫 클릭 = focus, 두 번째 = target. preview 안 띄움.
      if (!focus) setFocus(node.id);
      else if (!target && node.id !== focus) setTarget(node.id);
      else { setFocus(node.id); setTarget(null); }
      return;
    }
    if (node.id.startsWith("pkg:")) return;     // cluster supernode 무시 (다음 phase: expand)
    // 신규: 클릭 = bottom preview panel. focus 변경은 panel 의 "이 노드 중심" 버튼 또는 검색.
    const dto = (node.data as { node?: GraphNodeDTO } | undefined)?.node;
    if (!dto) return;
    if (pinned && previewNode && previewNode.id !== dto.id) return;  // 고정 시 갈아치움 X
    setPreviewNode(dto);
    // hover tooltip clear when commitment landed via click
    setHoverNode(null);
  }, [mode, focus, target, pinned, previewNode]);

  const onNodeMouseEnter = useCallback((e: React.MouseEvent, node: Node) => {
    if (node.id.startsWith("pkg:")) return;
    const dto = (node.data as { node?: GraphNodeDTO } | undefined)?.node;
    if (!dto) return;
    setHoverNode({ node: dto, x: e.clientX, y: e.clientY });
  }, []);

  const onNodeMouseLeave = useCallback(() => {
    setHoverNode(null);
  }, []);

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2 px-3 py-1.5 border-b border-border bg-card text-[11px]">
        {/* Mode toggle */}
        <div className="flex bg-muted rounded border border-border overflow-hidden">
          <ModeButton current={mode} value="neighborhood" label="이웃" icon={<Network className="w-3 h-3" />} onClick={() => { setMode("neighborhood"); setTarget(null); }} />
          <ModeButton current={mode} value="path" label="경로" icon={<GitFork className="w-3 h-3" />} onClick={() => setMode("path")} />
          <ModeButton current={mode} value="cluster" label="클러스터" icon={<Boxes className="w-3 h-3" />} onClick={() => { setMode("cluster"); setFocus(null); setTarget(null); }} />
        </div>

        {/* 검색 #1 (focus / path source) */}
        {mode !== "cluster" && (
          <div className="relative flex-1 min-w-[180px] max-w-xs">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-muted-foreground" />
            <Input
              value={searchQ}
              onChange={(e) => setSearchQ(e.target.value)}
              placeholder={mode === "path" ? "출발 노드" : "중심 노드 검색"}
              className="pl-7 h-7 text-xs"
            />
            {searchHits.length > 0 && (
              <div className="absolute left-0 right-0 top-full mt-1 bg-card border border-border rounded shadow-lg max-h-60 overflow-auto z-30">
                {searchHits.map((n) => (
                  <button
                    key={n.id}
                    onClick={() => { setFocus(n.id); setSearchQ(""); }}
                    className="w-full text-left px-2 py-1 text-[11px] hover:bg-muted flex items-center gap-1 border-b border-border last:border-b-0"
                  >
                    <KindDot kind={n.kind} />
                    <span className="truncate">{n.label}</span>
                    <span className="ml-auto text-muted-foreground text-[10px]">{n.kind}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* 검색 #2 (path target) */}
        {mode === "path" && focus && (
          <div className="relative flex-1 min-w-[180px] max-w-xs">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-muted-foreground" />
            <Input
              value={searchTargetQ}
              onChange={(e) => setSearchTargetQ(e.target.value)}
              placeholder="도착 노드"
              className="pl-7 h-7 text-xs"
            />
            {targetHits.length > 0 && (
              <div className="absolute left-0 right-0 top-full mt-1 bg-card border border-border rounded shadow-lg max-h-60 overflow-auto z-30">
                {targetHits.map((n) => (
                  <button
                    key={n.id}
                    onClick={() => { setTarget(n.id); setSearchTargetQ(""); }}
                    className="w-full text-left px-2 py-1 text-[11px] hover:bg-muted flex items-center gap-1 border-b border-border last:border-b-0"
                  >
                    <KindDot kind={n.kind} />
                    <span className="truncate">{n.label}</span>
                    <span className="ml-auto text-muted-foreground text-[10px]">{n.kind}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Focus / Target chip */}
        {focus && (
          <span className="flex items-center gap-1">
            <Target className="w-3 h-3 text-primary" />
            <code className="text-[10px] font-mono bg-muted px-1.5 py-0.5 rounded">
              {data?.nodes.find((n) => n.id === focus)?.label ?? focus.slice(-24)}
            </code>
            <button onClick={() => { setFocus(null); setTarget(null); }} className="text-muted-foreground hover:text-foreground">
              <X className="w-3 h-3" />
            </button>
          </span>
        )}
        {mode === "path" && target && (
          <>
            <span className="text-muted-foreground">→</span>
            <span className="flex items-center gap-1">
              <code className="text-[10px] font-mono bg-muted px-1.5 py-0.5 rounded">
                {data?.nodes.find((n) => n.id === target)?.label ?? target.slice(-24)}
              </code>
              <button onClick={() => setTarget(null)} className="text-muted-foreground hover:text-foreground">
                <X className="w-3 h-3" />
              </button>
            </span>
          </>
        )}

        {/* n_max slider — neighborhood only */}
        {mode === "neighborhood" && (
          <label className="flex items-center gap-1 text-muted-foreground">
            <span className="text-[10px]">노드</span>
            <select
              value={nMax}
              onChange={(e) => setNMax(Number(e.target.value))}
              className="bg-muted border border-border rounded px-1 py-0.5 text-[11px]"
            >
              <option value={20}>20</option>
              <option value={60}>60</option>
              <option value={150}>150</option>
              <option value={400}>400</option>
            </select>
          </label>
        )}

        {/* Perspective dropdown — R4-T3.4 */}
        <PerspectiveDropdown repoId={repoId} />

        {/* Compound 토글 — R4-T3.3 */}
        <label
          className="flex items-center gap-1 text-[11px] cursor-pointer"
          title="Domain (Java 패키지) 노드 안에 자식 클래스 nest"
        >
          <input
            type="checkbox"
            checked={compound}
            onChange={(e) => setCompound(e.target.checked)}
            className="cursor-pointer"
          />
          <Boxes className="w-3 h-3" />
          <span>패키지 묶음</span>
        </label>

        {/* Copy URL — R4-T2.3 */}
        <CopyUrlButton />

        {/* Counts */}
        <div className="ml-auto text-[10px] text-muted-foreground">
          {data ? (
            <>
              <NodeBadge kind="term" n={data.summary.nodes_term ?? 0} label="Term" />
              <NodeBadge kind="code_type" n={data.summary.nodes_code_type ?? 0} label="Code" />
              <NodeBadge kind="action" n={data.summary.nodes_action ?? 0} label="Action" />
              {(data.summary.nodes_domain ?? 0) > 0 && (
                <NodeBadge kind="domain" n={data.summary.nodes_domain ?? 0} label="Pkg" />
              )}
              <span className="ml-2 text-muted-foreground/70">
                · {data.summary.edges_total ?? 0} edges
              </span>
              {data.truncated && <span className="ml-2 text-amber-500">· truncated</span>}
            </>
          ) : "—"}
        </div>
      </div>

      {/* Graph */}
      <div className="flex-1 relative">
        {(loading || layoutBusy) && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/40 z-20 pointer-events-none">
            <Loader2 className="w-5 h-5 animate-spin text-primary" />
          </div>
        )}
        {err && (
          <div className="absolute inset-0 flex items-center justify-center text-xs text-destructive p-4 text-center">
            <div>
              <div className="font-medium mb-1">그래프 로드 실패</div>
              <div className="font-mono">{err}</div>
              <div className="mt-2 text-muted-foreground">
                먼저 Import + 추천 매핑 persist 가 필요합니다.
              </div>
            </div>
          </div>
        )}
        {!loading && !err && data && rfNodes.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center text-xs text-muted-foreground p-4 text-center">
            <div>
              빈 그래프 — Import + 「추천 매핑 persist」 로 BusinessTerm/Action/TypeRealization 후보를
              먼저 적재하세요.
            </div>
          </div>
        )}
        <ReactFlow
          // mode / focus / target / nMax / repo 변경 시 remount → fitView 재실행.
          key={`${repoId}|${mode}|${focus ?? ""}|${target ?? ""}|${nMax}|${rfNodes.length}`}
          nodes={rfNodes}
          edges={rfEdges}
          nodeTypes={NODE_TYPES}
          onNodeClick={onNodeClick}
          onNodeMouseEnter={onNodeMouseEnter}
          onNodeMouseLeave={onNodeMouseLeave}
          fitView
          fitViewOptions={{ padding: 0.18 }}
          proOptions={{ hideAttribution: true }}
          minZoom={0.1}
          maxZoom={2}
        >
          <Background gap={16} size={1} />
          <Controls position="bottom-left" />
          <MiniMap
            position="bottom-right"
            pannable
            zoomable
            nodeStrokeWidth={1}
            nodeColor={(n) => {
              const k = (n.data as { kind?: GraphNodeKind } | undefined)?.kind;
              return KIND_COLOR[k ?? "code_type"] ?? "#94a3b8";
            }}
            maskColor="rgba(0,0,0,0.4)"
            className="!bg-card !border !border-border"
          />
        </ReactFlow>
        {previewNode && data && (
          <NodePreviewPanel
            node={previewNode}
            edges={data.edges}
            allNodes={data.nodes}
            repoId={repoId}
            pinned={pinned}
            onClose={() => { setPreviewNode(null); setPinned(false); }}
            onTogglePin={() => setPinned((p) => !p)}
            onSetFocus={(fqn) => setFocus(fqn)}
            onMutated={() => setReloadTick((t) => t + 1)}
          />
        )}
        {hoverNode && data && (
          <HoverPreview node={hoverNode.node} x={hoverNode.x} y={hoverNode.y} edges={data.edges} />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Layout — ELK Layered (R4-T1.3 결정 B). compound on (R4-T3.3) 시 Domain 노드가
// children 으로 자식 CodeType 들 nest. contains edge 는 nesting 으로 표현 → 제외.
// ---------------------------------------------------------------------------
type ElkChild = {
  id: string;
  width?: number; height?: number;
  children?: ElkChild[];
  layoutOptions?: Record<string, string>;
};
type ElkOut = {
  id: string; x?: number; y?: number;
  width?: number; height?: number;
  children?: ElkOut[];
};

async function buildLayout(
  nodes: GraphNodeDTO[],
  edges: GraphEdgeDTO[],
  compound: boolean,
): Promise<{ rfNodes: Node[]; rfEdges: Edge[] }> {
  const elk = await getElk();

  // compound 시: Domain 노드의 members → 그 노드의 children. contains edge 제외.
  let elkChildren: ElkChild[];
  let elkEdges: { id: string; sources: string[]; targets: string[] }[];

  if (compound) {
    const memberSet = new Set<string>();
    const domainNodes = nodes.filter((n) => n.kind === "domain");
    const childMap: Record<string, string[]> = {};
    for (const d of domainNodes) {
      const members = ((d.extra as { members?: string[] } | undefined)?.members) ?? [];
      childMap[d.id] = members.filter((m) => nodes.some((n) => n.id === m));
      childMap[d.id].forEach((m) => memberSet.add(m));
    }
    const childById = new Map(nodes.map((n) => [n.id, n] as const));

    elkChildren = [
      // Domain compound nodes
      ...domainNodes.map<ElkChild>((d) => ({
        id: d.id,
        layoutOptions: {
          "elk.algorithm": "layered",
          "elk.direction": "DOWN",
          "elk.padding": "[top=28,left=8,bottom=8,right=8]",
          "elk.spacing.nodeNode": "20",
        },
        children: (childMap[d.id] ?? []).map((cid) => {
          const dto = childById.get(cid);
          return { id: cid, width: NODE_W, height: dto ? NODE_H : NODE_H };
        }),
      })),
      // 나머지 (Term / Action / 미nest CodeType) 은 root level
      ...nodes
        .filter((n) => n.kind !== "domain" && !memberSet.has(n.id))
        .map<ElkChild>((n) => ({ id: n.id, width: NODE_W, height: NODE_H })),
    ];
    // contains edge 는 nesting 으로 충분 — visualization 제외
    elkEdges = edges
      .filter((e) => e.kind !== "contains")
      .map((e, i) => ({ id: `e${i}`, sources: [e.source], targets: [e.target] }));
  } else {
    elkChildren = nodes.map((n) => ({ id: n.id, width: NODE_W, height: NODE_H }));
    elkEdges = edges.map((e, i) => ({ id: `e${i}`, sources: [e.source], targets: [e.target] }));
  }

  const root = {
    id: "root",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "DOWN",
      "elk.layered.spacing.nodeNodeBetweenLayers": "70",
      "elk.spacing.nodeNode": "32",
      "elk.padding": "[top=12,left=12,bottom=12,right=12]",
      "elk.hierarchyHandling": "INCLUDE_CHILDREN",
    },
    children: elkChildren,
    edges: elkEdges,
  };

  const result = (await elk.layout(root)) as ElkOut;

  const rfNodes: Node[] = [];
  const visit = (laid: ElkOut, parentId?: string) => {
    if (laid.id === "root") {
      laid.children?.forEach((c) => visit(c, undefined));
      return;
    }
    const dto = nodes.find((n) => n.id === laid.id);
    if (!dto) return;
    if (dto.kind === "domain" && compound && (laid.children?.length ?? 0) > 0) {
      // group node — 자식 위치는 ELK 가 부모 기준 상대좌표
      rfNodes.push({
        id: laid.id,
        type: "domainGroup",
        position: { x: laid.x ?? 0, y: laid.y ?? 0 },
        data: { node: dto, kind: "domain" },
        style: { width: laid.width ?? NODE_W, height: laid.height ?? NODE_H, zIndex: -1 },
        parentId,
        extent: parentId ? "parent" : undefined,
        draggable: true,
        selectable: true,
      });
      laid.children?.forEach((c) => visit(c, laid.id));
    } else {
      rfNodes.push({
        id: laid.id,
        type: "ontology",
        position: { x: laid.x ?? 0, y: laid.y ?? 0 },
        data: { node: dto, kind: dto.kind },
        parentId,
        extent: parentId ? "parent" : undefined,
        draggable: true,
      });
    }
  };
  visit(result);

  const rfEdges: Edge[] = edges
    .filter((e) => !compound || e.kind !== "contains")  // compound 시 contains 제외
    .map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      type: "smoothstep",
      label: e.label ?? edgeKindLabel(e.kind),
      labelStyle: { fontSize: 9, fill: "var(--color-muted-foreground)" },
      style: { stroke: edgeKindColor(e.kind), strokeWidth: edgeKindWidth(e.kind) },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        width: 12,
        height: 12,
        color: edgeKindColor(e.kind),
      } as EdgeMarkerType,
      animated: e.kind === "type_realization_partial",
    }));

  return { rfNodes, rfEdges };
}

// ---------------------------------------------------------------------------
// Custom Node
// ---------------------------------------------------------------------------
type NodeData = { node: GraphNodeDTO; kind: GraphNodeKind };

const KIND_COLOR: Record<GraphNodeKind, string> = {
  term: "#a78bfa",       // violet — domain concept
  code_type: "#fbbf24",  // amber — code
  action: "#fb923c",     // orange — verb
  domain: "#64748b",     // slate — Java 패키지 그룹 (R4-T3.1)
};

function OntologyNode({ data }: NodeProps) {
  const d = data as NodeData;
  const n = d.node;
  const color = KIND_COLOR[n.kind];
  const subtitle = nodeSubtitle(n);

  // Term 의 atomic 은 pill 모양 (rounded-full), composite 는 사각.
  // Domain 은 다른 모양 — 굵은 outline + dashed border.
  const isAtomicTerm = n.kind === "term" && n.role === "atomic";
  const isDomain = n.kind === "domain";

  return (
    <div
      className={cn(
        "border-l-[3px] border bg-card px-2 py-1 text-[11px] shadow-sm overflow-hidden",
        isAtomicTerm ? "rounded-full" : "rounded",
        isDomain && "border-dashed bg-slate-500/10",
        n.confirmed && !isDomain ? "border-emerald-500/40" : "border-border",
      )}
      style={{ width: NODE_W, height: NODE_H, borderLeftColor: color }}
    >
      <Handle type="target" position={Position.Top} style={{ background: color }} />
      <div className="font-medium truncate">
        {isDomain && <span className="text-slate-400 mr-1">📦</span>}
        {n.label}
      </div>
      <div className="text-[9.5px] text-muted-foreground truncate flex items-center gap-1">
        <KindDot kind={n.kind} />
        {subtitle}
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: color }} />
    </div>
  );
}

function DomainGroupNode({ data }: NodeProps) {
  const d = data as NodeData;
  const n = d.node;
  const cnt = (n.extra as { class_count?: number } | undefined)?.class_count ?? 0;
  return (
    <div
      className="rounded border-2 border-dashed border-slate-500 bg-slate-500/5 w-full h-full relative pointer-events-auto"
    >
      <div className="absolute top-0 left-0 right-0 px-2 py-1 text-[11px] font-semibold text-slate-300 bg-slate-700/40 border-b border-slate-500/40 truncate">
        📦 {n.label}
        <span className="text-[9.5px] text-slate-400 ml-1.5 font-normal">({cnt} class)</span>
      </div>
    </div>
  );
}

const NODE_TYPES = { ontology: OntologyNode, domainGroup: DomainGroupNode };

function nodeSubtitle(n: GraphNodeDTO): string {
  const parts: string[] = [];
  if (n.kind === "code_type") {
    const pkgTail = (n.domain ?? "").split(".").slice(-2).join(".");
    parts.push(pkgTail || "code_type");
    if (n.role && n.role !== "domain") parts.push(n.role);
  } else if (n.kind === "term") {
    parts.push(n.role === "atomic" ? "atomic" : "composite");
    if (n.extra?.is_root_entity) parts.push("root");
    if (n.extra?.struct_like_hint) parts.push("struct");
  } else if (n.kind === "domain") {
    const cnt = (n.extra as { class_count?: number } | undefined)?.class_count ?? 0;
    parts.push(`패키지 · ${cnt} class`);
  } else {
    parts.push("action");
    if (n.role) parts.push(n.role);
    if (typeof n.extra?.verification === "string") parts.push(n.extra.verification);
  }
  return parts.join(" · ");
}

// P3 폴리싱: hover 시 노드 위에 떠오르는 빠른 미리보기. click 으로 NodePreviewPanel
// (full info) 에 commit 하기 전 빠른 확인용.
function HoverPreview({
  node,
  x,
  y,
  edges,
}: {
  node: GraphNodeDTO;
  x: number;
  y: number;
  edges: GraphEdgeDTO[];
}) {
  // Count incoming + outgoing edges for a quick "how connected?" hint.
  const incoming = edges.filter((e) => e.target === node.id).length;
  const outgoing = edges.filter((e) => e.source === node.id).length;
  // Position 12px up-right of the cursor; flip leftward if too close to the
  // viewport edge so the tooltip doesn't get clipped.
  const TIP_W = 280;
  const flipLeft = typeof window !== "undefined" && x + TIP_W + 24 > window.innerWidth;
  const left = flipLeft ? x - TIP_W - 12 : x + 12;
  const top = Math.max(8, y - 24);
  return (
    <div
      className="fixed z-50 pointer-events-none rounded-md border border-border bg-card shadow-lg px-3 py-2 text-[11px]"
      style={{ left, top, width: TIP_W }}
    >
      <div className="flex items-center gap-1.5 mb-1">
        <KindDot kind={node.kind} />
        <span className="font-mono text-[11px] text-foreground truncate">{node.label}</span>
      </div>
      <div className="text-[10.5px] text-muted-foreground truncate">
        {nodeSubtitle(node)}
      </div>
      <div className="text-[10px] text-muted-foreground mt-1 flex items-center gap-2.5">
        <span>edges: ⇠ {incoming} · ⇢ {outgoing}</span>
        {node.domain && (
          <span className="truncate flex-1">domain: {node.domain}</span>
        )}
      </div>
      <div className="text-[10px] text-muted-foreground italic mt-1">
        클릭하면 자세히 보기
      </div>
    </div>
  );
}

function KindDot({ kind }: { kind: GraphNodeKind }) {
  return (
    <span
      className="inline-block rounded-full"
      style={{ width: 6, height: 6, background: KIND_COLOR[kind] }}
    />
  );
}

function CopyUrlButton() {
  const [copied, setCopied] = useState(false);
  const onClick = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      // ignore
    }
  };
  return (
    <button
      onClick={onClick}
      title="현 view URL 복사 (붙여넣어 공유)"
      className={cn(
        "flex items-center gap-1 px-2 py-0.5 rounded border text-[11px] transition",
        copied
          ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-400"
          : "bg-muted border-border text-muted-foreground hover:text-foreground",
      )}
    >
      {copied ? <Check className="w-3 h-3" /> : <Link2 className="w-3 h-3" />}
      <span>{copied ? "복사됨" : "URL"}</span>
    </button>
  );
}

function ModeButton({
  current, value, label, icon, onClick,
}: { current: GraphViewMode; value: GraphViewMode; label: string; icon: React.ReactNode; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "px-2 py-1 text-[11px] flex items-center gap-1 transition",
        current === value
          ? "bg-primary text-primary-foreground"
          : "text-muted-foreground hover:text-foreground",
      )}
    >
      {icon}
      <span>{label}</span>
    </button>
  );
}

function NodeBadge({
  kind,
  n,
  label,
}: { kind: GraphNodeKind; n: number; label: string }) {
  return (
    <span className="inline-flex items-center gap-1 mr-2">
      <KindDot kind={kind} />
      <span className="font-mono">{n}</span>
      <span className="text-muted-foreground/70">{label}</span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// Edge style
// ---------------------------------------------------------------------------
function edgeKindLabel(k: GraphEdgeDTO["kind"]): string | undefined {
  switch (k) {
    case "extends":                    return "extends";
    case "implements":                 return "implements";
    case "composition":                return "has";
    case "type_realization_primary":   return "PRIMARY";
    case "type_realization_partial":   return "PARTIAL";
    case "realization":                return "impl";
    case "contains":                   return undefined;  // 너무 많아서 라벨 생략
    default:                           return undefined;
  }
}

function edgeKindColor(k: GraphEdgeDTO["kind"]): string {
  switch (k) {
    case "extends":                    return "#94a3b8";
    case "implements":                 return "#cbd5e1";
    case "composition":                return "#a78bfa";
    case "type_realization_primary":   return "#10b981";  // emerald
    case "type_realization_partial":   return "#f59e0b";  // amber (partial = noteworthy)
    case "realization":                return "#fb923c";  // orange
    case "contains":                   return "#475569";  // slate dim — 패키지 → 클래스
    default:                           return "#94a3b8";
  }
}

function edgeKindWidth(k: GraphEdgeDTO["kind"]): number {
  if (k === "type_realization_primary") return 2;
  if (k === "type_realization_partial") return 1.8;
  if (k === "realization")              return 1.5;
  return 1;
}
