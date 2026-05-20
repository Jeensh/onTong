"use client";

/**
 * Impact mode — graph redesign Option 3 의 "event-driven ripple".
 *
 * focus entity 중심 양방향 BFS. match_kind 5단계 strength + risk decay.
 * 좌측: 간단한 distance 기반 xyflow 그래프 (focus 중앙, backward 좌측, forward 우측)
 * 우측: risk top / 재검증 대상 / lazy method expand 토글
 *
 * Backend: GET /graph/impact + /graph/impact/expand-method.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type Edge,
  MarkerType,
  type EdgeMarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Loader2, RotateCw, X, ArrowLeftRight, ArrowLeft, ArrowRight, Shield, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  ontologyApi,
  type ImpactResponseDTO,
  type ImpactNodeDTO,
  type ImpactEdgeDTO,
  type MethodNodeDTO,
} from "@/lib/api/ontology";
import {
  useWorkbench,
  type ImpactDirection,
  type ImpactFocusKind,
} from "./store";

const KIND_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  action:      { bg: "bg-violet-100",  border: "border-violet-400",  text: "text-violet-900" },
  term:        { bg: "bg-emerald-100", border: "border-emerald-400", text: "text-emerald-900" },
  code_type:   { bg: "bg-slate-100",   border: "border-slate-400",   text: "text-slate-900" },
  code_method: { bg: "bg-sky-100",     border: "border-sky-400",     text: "text-sky-900" },
};

const MATCH_KIND_COLOR: Record<string, string> = {
  receiver_exact:    "#0ea5e9", // sky-500 — 가장 강함
  receiver_short:    "#06b6d4", // cyan-500
  runtime_type:      "#10b981", // emerald-500
  package_proximity: "#f59e0b", // amber-500
  name_only:         "#f87171", // red-400 — 약함
};

export function ImpactView({ repoId }: { repoId: string }) {
  const focusFqn = useWorkbench((s) => s.impactFocusFqn);
  const focusKind = useWorkbench((s) => s.impactFocusKind);
  const hops = useWorkbench((s) => s.impactHops);
  const direction = useWorkbench((s) => s.impactDirection);
  const minStrength = useWorkbench((s) => s.impactMinStrength);
  const includeMethods = useWorkbench((s) => s.impactIncludeMethods);
  const expandedTypes = useWorkbench((s) => s.impactExpandedTypes);
  const setHops = useWorkbench((s) => s.setImpactHops);
  const setDirection = useWorkbench((s) => s.setImpactDirection);
  const setMinStrength = useWorkbench((s) => s.setImpactMinStrength);
  const setIncludeMethods = useWorkbench((s) => s.setImpactIncludeMethods);
  const toggleExpandedType = useWorkbench((s) => s.toggleImpactExpandedType);
  const resetImpact = useWorkbench((s) => s.resetImpact);
  const jumpToImpact = useWorkbench((s) => s.jumpToImpact);

  const [data, setData] = useState<ImpactResponseDTO | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [reloadTick, setReloadTick] = useState(0);

  useEffect(() => {
    if (!focusFqn) {
      setData(null);
      setErr(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setErr(null);
    ontologyApi
      .getImpact(repoId, {
        focus: focusFqn,
        focus_kind: focusKind,
        hops,
        direction,
        min_strength: minStrength,
        include_methods: includeMethods,
      })
      .then((d) => {
        if (cancelled) return;
        setData(d);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setErr(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [repoId, focusFqn, focusKind, hops, direction, minStrength, includeMethods, reloadTick]);

  // No focus → guidance panel
  if (!focusFqn) {
    return (
      <div className="flex items-center justify-center h-full p-6">
        <div className="max-w-md text-center space-y-3">
          <Waves className="w-10 h-10 text-muted-foreground mx-auto" />
          <h3 className="text-sm font-semibold">변경 영향 분석 (Impact)</h3>
          <p className="text-xs text-muted-foreground leading-relaxed">
            entity 하나를 focus 로 골라 양방향 ripple 을 분석합니다.
            <br />
            Coverage 탭에서 entity 의 <b>Impact</b> 버튼을 누르거나,
            아래 빠른 진입에서 검색하세요.
          </p>
          <p className="text-[11px] text-muted-foreground">
            (백엔드 BFS: receiver_exact / receiver_short / runtime_type /
            package_proximity / name_only 5 단계 strength · risk = base × strength /
            (distance+1))
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="px-3 py-1.5 bg-card border-b border-border flex items-center gap-3 flex-wrap text-[11px]">
        <span className="flex items-center gap-1">
          <span className="text-muted-foreground">focus</span>
          <span
            className={cn(
              "px-1.5 py-0.5 rounded font-mono text-[10px] border",
              KIND_COLORS[focusKind]?.bg,
              KIND_COLORS[focusKind]?.border,
              KIND_COLORS[focusKind]?.text,
            )}
            title={focusFqn}
          >
            {focusKind}
          </span>
          <code className="font-mono text-[10px] bg-muted px-1.5 py-0.5 rounded max-w-xs truncate" title={focusFqn}>
            {data?.focus.label || focusFqn}
          </code>
          <button onClick={resetImpact} className="text-muted-foreground hover:text-foreground" title="focus 해제">
            <X className="w-3 h-3" />
          </button>
        </span>

        <div className="flex items-center gap-1 ml-2">
          <DirectionButton current={direction} value="backward" onClick={() => setDirection("backward")} icon={<ArrowLeft className="w-3 h-3" />} label="Backward" />
          <DirectionButton current={direction} value="both" onClick={() => setDirection("both")} icon={<ArrowLeftRight className="w-3 h-3" />} label="Both" />
          <DirectionButton current={direction} value="forward" onClick={() => setDirection("forward")} icon={<ArrowRight className="w-3 h-3" />} label="Forward" />
        </div>

        <label className="flex items-center gap-1 text-muted-foreground">
          hops
          <select
            value={hops}
            onChange={(e) => setHops(Number(e.target.value))}
            className="bg-background border rounded h-6 px-1 text-[11px]"
          >
            {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>

        <label className="flex items-center gap-1 text-muted-foreground">
          min strength
          <select
            value={minStrength}
            onChange={(e) => setMinStrength(Number(e.target.value))}
            className="bg-background border rounded h-6 px-1 text-[11px]"
          >
            <option value={0}>0.0 (모두)</option>
            <option value={0.5}>0.5</option>
            <option value={0.7}>0.7</option>
            <option value={0.85}>0.85</option>
            <option value={0.95}>0.95 (엄격)</option>
          </select>
        </label>

        <label className="flex items-center gap-1 text-muted-foreground">
          <input
            type="checkbox"
            checked={includeMethods}
            onChange={(e) => setIncludeMethods(e.target.checked)}
            className="h-3 w-3"
          />
          method 노드 포함
        </label>

        <div className="ml-auto flex items-center gap-2 text-muted-foreground">
          {data && (
            <span>
              {data.nodes.length} 노드 · {data.edges.length} 엣지
              {data.truncated_at_hop && (
                <span className="text-amber-600 ml-1">(hop {data.truncated_at_hop} truncated)</span>
              )}
            </span>
          )}
          <Button size="sm" variant="outline" className="h-6 px-2" onClick={() => setReloadTick((t) => t + 1)}>
            <RotateCw className="w-3 h-3" />
          </Button>
        </div>
      </div>

      {/* Body: graph + sidebar */}
      <div className="flex-1 flex min-h-0">
        <div className="flex-1 relative">
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-background/40 z-10 text-[11px] text-muted-foreground">
              <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Impact 분석중…
            </div>
          )}
          {err && (
            <div className="absolute inset-0 flex flex-col items-center justify-center text-rose-700 gap-2 z-10">
              <span className="text-sm">분석 실패: {err}</span>
              <Button size="sm" variant="outline" onClick={() => setReloadTick((t) => t + 1)}>
                <RotateCw className="w-3 h-3 mr-1" /> 재시도
              </Button>
            </div>
          )}
          {data && <ImpactCanvas data={data} onNodeFocus={jumpToImpact} />}
        </div>
        <ImpactSidebar
          data={data}
          repoId={repoId}
          expandedTypes={expandedTypes}
          onToggleExpand={toggleExpandedType}
          onNodeFocus={jumpToImpact}
        />
      </div>
    </div>
  );
}

function Waves(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M2 6c2 0 2 2 5 2s3-2 5-2 3 2 5 2 3-2 5-2" />
      <path d="M2 12c2 0 2 2 5 2s3-2 5-2 3 2 5 2 3-2 5-2" />
      <path d="M2 18c2 0 2 2 5 2s3-2 5-2 3 2 5 2 3-2 5-2" />
    </svg>
  );
}

function DirectionButton({
  current, value, onClick, icon, label,
}: {
  current: ImpactDirection;
  value: ImpactDirection;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  const active = current === value;
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex items-center gap-1 px-1.5 py-0.5 rounded border transition-colors",
        active ? "bg-primary text-primary-foreground border-primary" : "bg-transparent border-transparent hover:bg-muted text-muted-foreground",
      )}
      title={label}
    >
      {icon}
      <span className="text-[10px]">{label}</span>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Canvas — distance-based layout (focus 중앙, backward 좌측, forward 우측)
// ---------------------------------------------------------------------------
const NODE_W = 200;
const NODE_H = 44;
const X_GAP = 240;
const Y_GAP = 60;

// fitView 옵션은 정적 — props 마다 새 객체 만들면 ReactFlow 가 refit 을 매번 트리거.
const FIT_VIEW_OPTS = { padding: 0.15, duration: 0, maxZoom: 1.5 } as const;

function ImpactCanvas({
  data,
  onNodeFocus,
}: {
  data: ImpactResponseDTO;
  onNodeFocus: (fqn: string, kind: ImpactFocusKind) => void;
}) {
  const { rfNodes, rfEdges } = useMemo(() => layoutImpact(data), [data]);

  const onNodeDoubleClick = useCallback(
    (_e: React.MouseEvent, node: Node) => {
      const dto = (node.data as { node?: ImpactNodeDTO } | undefined)?.node;
      if (!dto) return;
      const kind = (dto.kind === "code_type" || dto.kind === "code_method" || dto.kind === "term" || dto.kind === "action") ? dto.kind : "action";
      onNodeFocus(dto.fqn, kind);
    },
    [onNodeFocus],
  );

  // focus 가 바뀌면 그래프를 완전히 갈아엎는 게 더 빠름 (xyflow diff 1K+ 노드 비싸짐).
  // key 로 re-mount → 새 그래프는 항상 처음부터 fitView.
  return (
    <ReactFlow
      key={data.focus.fqn}
      nodes={rfNodes}
      edges={rfEdges}
      fitView
      fitViewOptions={FIT_VIEW_OPTS}
      onNodeDoubleClick={onNodeDoubleClick}
      nodesDraggable
      panOnDrag
      zoomOnScroll
      proOptions={{ hideAttribution: true }}
      defaultEdgeOptions={DEFAULT_EDGE_OPTIONS}
    >
      <Background />
      <Controls showInteractive={false} />
    </ReactFlow>
  );
}

const DEFAULT_EDGE_OPTIONS = { type: "default" } as const;

function layoutImpact(data: ImpactResponseDTO): { rfNodes: Node[]; rfEdges: Edge[] } {
  // bucket nodes by (direction, distance)
  // x = signed distance * X_GAP (backward 음수, forward 양수, focus 0)
  // y = bucket 안의 index
  const buckets = new Map<string, ImpactNodeDTO[]>(); // key: dir|dist
  for (const n of data.nodes) {
    const sign = n.direction === "backward" ? -1 : n.direction === "forward" ? 1 : 0;
    const key = `${sign}|${n.distance}`;
    const list = buckets.get(key) ?? [];
    list.push(n);
    buckets.set(key, list);
  }

  const rfNodes: Node[] = [];
  for (const [key, list] of buckets) {
    const [signStr, distStr] = key.split("|");
    const sign = Number(signStr);
    const dist = Number(distStr);
    const x = sign * dist * X_GAP;
    list.forEach((n, idx) => {
      const tone = KIND_COLORS[n.kind] ?? KIND_COLORS.action;
      rfNodes.push({
        id: n.id,
        position: { x, y: (idx - (list.length - 1) / 2) * Y_GAP },
        data: { node: n, label: n.label },
        style: {
          width: NODE_W,
          height: NODE_H,
          padding: 0,
          fontSize: 11,
          borderRadius: 6,
          border: n.distance === 0 ? "2px solid #6366f1" : "1px solid",
        },
        type: "default",
        className: cn(tone.bg, tone.border, tone.text, "border"),
      });
    });
  }

  // 200+ edge 에서 label/marker/animated 다 켜면 페인트 비용 폭증. dense 모드로 감산.
  const dense = data.edges.length > 200;
  const rfEdges: Edge[] = data.edges.map((e) => {
    const color = e.match_kind ? MATCH_KIND_COLOR[e.match_kind] ?? "#94a3b8" : "#94a3b8";
    const edge: Edge = {
      id: e.id,
      source: e.source,
      target: e.target,
      style: {
        stroke: color,
        strokeWidth: 0.6 + e.strength * 1.4,
        opacity: 0.35 + e.strength * 0.55,
      },
    };
    if (!dense) {
      edge.label = e.match_kind ? `${e.match_kind} ${e.strength.toFixed(2)}` : e.kind;
      edge.labelStyle = { fontSize: 9, fill: "#475569" };
      edge.labelBgStyle = { fill: "#f8fafc", fillOpacity: 0.9 };
    }
    // marker 는 strength 상위 (≥0.85) 또는 sparse 모드에서만. 약한 엣지는 무방향처럼 보임.
    if (e.strength >= 0.85 || !dense) {
      edge.markerEnd = { type: MarkerType.ArrowClosed, color } as EdgeMarkerType;
    }
    // animated 는 강한 엣지 중에서도 상위만 — dense 면 비활성, sparse 면 ≥0.85 켜기
    if (!dense && e.strength >= 0.85) {
      edge.animated = true;
    }
    return edge;
  });

  return { rfNodes, rfEdges };
}

// ---------------------------------------------------------------------------
// Sidebar — risk top + 재검증 + method expand
// ---------------------------------------------------------------------------
function ImpactSidebar({
  data,
  repoId,
  expandedTypes,
  onToggleExpand,
  onNodeFocus,
}: {
  data: ImpactResponseDTO | null;
  repoId: string;
  expandedTypes: string[];
  onToggleExpand: (fqn: string) => void;
  onNodeFocus: (fqn: string, kind: ImpactFocusKind) => void;
}) {
  if (!data) {
    return (
      <aside className="w-80 border-l border-border bg-card overflow-y-auto p-3 text-[11px] text-muted-foreground">
        분석 대기중…
      </aside>
    );
  }

  return (
    <aside className="w-80 border-l border-border bg-card overflow-y-auto p-3 space-y-4 text-[11px]">
      {/* Summary */}
      <section className="space-y-1">
        <h4 className="font-semibold text-[12px] text-foreground">Summary</h4>
        <ul className="text-muted-foreground space-y-0.5">
          <li>forward (영향 받는 것): {data.forward_count}</li>
          <li>backward (영향 주는 것): {data.backward_count}</li>
          <li>총 노드: {data.nodes.length}</li>
        </ul>
      </section>

      {/* Risk top */}
      <section className="space-y-1">
        <h4 className="font-semibold text-[12px] text-foreground flex items-center gap-1">
          <Shield className="w-3.5 h-3.5 text-rose-600" /> 위험 Top
        </h4>
        {data.risk_top.length === 0 ? (
          <div className="text-muted-foreground italic">없음</div>
        ) : (
          <ul className="space-y-0.5">
            {data.risk_top.slice(0, 12).map((r) => (
              <li
                key={`${r.kind}|${r.fqn}`}
                className="flex items-center gap-1.5 px-1 py-0.5 hover:bg-muted rounded cursor-pointer"
                onClick={() => onNodeFocus(r.fqn, (r.kind as ImpactFocusKind) ?? "action")}
                title="새 focus 로 이동"
              >
                <span
                  className={cn(
                    "text-[9px] px-1 rounded font-mono shrink-0",
                    KIND_COLORS[r.kind]?.bg,
                    KIND_COLORS[r.kind]?.text,
                  )}
                >
                  {r.kind === "code_type" ? "type" : r.kind === "code_method" ? "m" : r.kind}
                </span>
                <span className="truncate font-mono text-[10px]" title={r.fqn}>
                  {r.label || r.fqn.split(".").slice(-2).join(".")}
                </span>
                <span className="ml-auto font-mono text-rose-700 text-[10px] shrink-0">
                  {r.risk_score.toFixed(2)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Re-verify */}
      <section className="space-y-1">
        <h4 className="font-semibold text-[12px] text-foreground">재검증 대상</h4>
        {data.re_verify_targets.length === 0 ? (
          <div className="text-muted-foreground italic">없음 (confirmed anchor 미발견)</div>
        ) : (
          <ul className="space-y-0.5">
            {data.re_verify_targets.map((t) => (
              <li
                key={`${t.kind}|${t.fqn}`}
                className="flex items-center gap-1.5 px-1 py-0.5 hover:bg-muted rounded cursor-pointer"
                onClick={() => onNodeFocus(t.fqn, (t.kind as ImpactFocusKind) ?? "code_method")}
              >
                <span className="text-[9px] px-1 rounded font-mono bg-amber-100 text-amber-800 shrink-0">
                  {t.kind === "code_method" ? "m" : t.kind}
                </span>
                <span className="truncate font-mono text-[10px]" title={t.fqn}>
                  {t.fqn.split(".").slice(-2).join(".")}
                </span>
                {t.reason && (
                  <span className="ml-auto text-[9px] text-muted-foreground shrink-0">
                    {t.reason}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Method expand */}
      {data.expand_method_targets.length > 0 && (
        <section className="space-y-1">
          <h4 className="font-semibold text-[12px] text-foreground">메서드 확장</h4>
          <ul className="space-y-0.5">
            {data.expand_method_targets.map((fqn) => (
              <MethodExpandRow
                key={fqn}
                repoId={repoId}
                codeTypeFqn={fqn}
                expanded={expandedTypes.includes(fqn)}
                onToggle={() => onToggleExpand(fqn)}
                onMethodFocus={(mfqn) => onNodeFocus(mfqn, "code_method")}
              />
            ))}
          </ul>
        </section>
      )}
    </aside>
  );
}

function MethodExpandRow({
  repoId,
  codeTypeFqn,
  expanded,
  onToggle,
  onMethodFocus,
}: {
  repoId: string;
  codeTypeFqn: string;
  expanded: boolean;
  onToggle: () => void;
  onMethodFocus: (method_fqn: string) => void;
}) {
  const [data, setData] = useState<MethodNodeDTO[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!expanded || data !== null) return;
    let cancelled = false;
    setLoading(true);
    setErr(null);
    ontologyApi
      .expandImpactMethods(repoId, codeTypeFqn)
      .then((d) => {
        if (cancelled) return;
        setData(d.methods);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setErr(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [expanded, repoId, codeTypeFqn, data]);

  return (
    <li className="border rounded text-[10px]">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-1 px-1.5 py-1 hover:bg-muted text-left"
      >
        <ChevronDown className={cn("w-3 h-3 shrink-0 transition-transform", !expanded && "-rotate-90")} />
        <span className="truncate font-mono" title={codeTypeFqn}>
          {codeTypeFqn.split(".").slice(-2).join(".")}
        </span>
      </button>
      {expanded && (
        <div className="border-t px-2 py-1 space-y-0.5 bg-muted/30">
          {loading && <span className="text-muted-foreground"><Loader2 className="inline w-3 h-3 mr-1 animate-spin" />로딩…</span>}
          {err && <span className="text-rose-700">실패: {err}</span>}
          {!loading && !err && data && data.length === 0 && (
            <span className="text-muted-foreground italic">메서드 없음</span>
          )}
          {!loading && !err && data && data.map((m) => (
            <div
              key={m.fqn}
              className="flex items-center gap-1 px-1 py-0.5 hover:bg-white rounded cursor-pointer"
              onClick={() => onMethodFocus(m.fqn)}
              title={m.fqn}
            >
              {m.has_anchor && <Shield className="w-2.5 h-2.5 text-amber-600 shrink-0" />}
              <span className="font-mono truncate">{m.name}</span>
              <span className="ml-auto text-muted-foreground text-[9px] shrink-0">{m.role}</span>
            </div>
          ))}
        </div>
      )}
    </li>
  );
}
