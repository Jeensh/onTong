"use client";

/**
 * Bottom slide-up preview panel for graph mode (R4-T2.1, 안건 3 B).
 *
 * 그래프 모드에서 노드 클릭 시 화면 하단 240px slide-up.
 * - 노드 essentials + 1줄 요약 + 인접 카운트
 * - quick action: focus / Detail 모드 열기 / 큐 confirm/reject (해당 시)
 * - pin (다음 노드 클릭 시 갈아치움 안 됨), 닫기
 */
import { useEffect, useMemo, useState } from "react";
import {
  X, Pin, PinOff, Target, ExternalLink, Check,
  XCircle, Loader2, AlertCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  ontologyApi,
  type GraphEdgeDTO,
  type GraphNodeDTO,
  type GraphNodeKind,
  type ActionDTO,
  type CodeTypeDTO,
  type TermDTO,
} from "@/lib/api/ontology";
import { useWorkbench } from "./store";

const PANEL_HEIGHT = 240;

const KIND_COLOR: Record<GraphNodeKind, string> = {
  term: "#a78bfa",
  code_type: "#fbbf24",
  action: "#fb923c",
  domain: "#64748b",
};

const KIND_LABEL_KO: Record<GraphNodeKind, string> = {
  term: "Term",
  code_type: "Code",
  action: "Action",
  domain: "Pkg",
};

interface Props {
  node: GraphNodeDTO;
  edges: GraphEdgeDTO[];          // 전체 그래프 edges (이웃 카운트 계산)
  allNodes: GraphNodeDTO[];        // 인접 노드 lookup
  repoId: string;
  pinned: boolean;
  onClose: () => void;
  onTogglePin: () => void;
  onSetFocus: (fqn: string) => void;
  /** 큐에서 confirm/reject 후 그래프 reload 필요 시 호출 */
  onMutated?: () => void;
}

export function NodePreviewPanel({
  node, edges, allNodes, repoId, pinned, onClose, onTogglePin, onSetFocus, onMutated,
}: Props) {
  const setSelectedAction = useWorkbench((s) => s.setSelectedAction);
  const setSelectedCodeType = useWorkbench((s) => s.setSelectedCodeType);
  const setSelectedTerm = useWorkbench((s) => s.setSelectedTerm);
  const setGraphMode = useWorkbench((s) => s.setGraphMode);

  // 추가 detail load (kind 별 endpoint)
  const [detail, setDetail] = useState<TermDTO | CodeTypeDTO | ActionDTO | null>(null);
  const [loading, setLoading] = useState(false);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [actionFeedback, setActionFeedback] = useState<{ type: "ok" | "err"; msg: string } | null>(null);

  useEffect(() => {
    let cancelled = false;
    setDetail(null);
    setLoading(true);
    setActionFeedback(null);
    const fetcher = (
      node.kind === "term" ? ontologyApi.getTerm(node.id) :
      node.kind === "code_type" ? ontologyApi.getCodeType(node.id) :
      ontologyApi.getAction(node.id)
    );
    fetcher
      .then((d) => { if (!cancelled) setDetail(d); })
      .catch(() => { if (!cancelled) setDetail(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [node.id, node.kind]);

  // 인접 노드 카운트 (1-hop) — kind 별
  const neighborCounts = useMemo(() => {
    const adj = new Set<string>();
    for (const e of edges) {
      if (e.source === node.id) adj.add(e.target);
      else if (e.target === node.id) adj.add(e.source);
    }
    const counts: Record<GraphNodeKind, number> = { term: 0, code_type: 0, action: 0, domain: 0 };
    for (const id of adj) {
      const n = allNodes.find((x) => x.id === id);
      if (n) counts[n.kind] += 1;
    }
    return counts;
  }, [node.id, edges, allNodes]);

  // 직접 연결된 edge 종류 카운트
  const edgeKindCounts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const e of edges) {
      if (e.source === node.id || e.target === node.id) {
        c[e.kind] = (c[e.kind] ?? 0) + 1;
      }
    }
    return c;
  }, [node.id, edges]);

  const openInDetail = () => {
    if (node.kind === "action") setSelectedAction(node.id);
    else if (node.kind === "code_type") setSelectedCodeType(node.id);
    else setSelectedTerm(node.id);
    setGraphMode(false);
  };

  // 큐 confirm/reject (term + action 만 확정 가능)
  const isUnconfirmedTerm = node.kind === "term" && (detail as TermDTO | null)?.confirmed === false;
  const isUnconfirmedAction =
    node.kind === "action" && detail !== null && !("confirmed_by" in detail ? detail.confirmed_by : true);

  const doConfirm = async () => {
    setBusyAction("confirm");
    try {
      if (node.kind === "term") {
        await ontologyApi.confirmTerm(repoId, node.id);
      } else if (node.kind === "action") {
        await ontologyApi.confirmActionCandidate(repoId, node.id);
      }
      setActionFeedback({ type: "ok", msg: "확정됨" });
      onMutated?.();
    } catch (e) {
      setActionFeedback({ type: "err", msg: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusyAction(null);
    }
  };

  const doReject = async () => {
    if (!confirm(`${node.label} 후보를 거절하시겠습니까? (삭제됨)`)) return;
    setBusyAction("reject");
    try {
      if (node.kind === "term") {
        await ontologyApi.rejectTerm(repoId, node.id);
      } else if (node.kind === "action") {
        await ontologyApi.rejectActionCandidate(repoId, node.id);
      }
      setActionFeedback({ type: "ok", msg: "거절됨 (큐에서 삭제)" });
      onMutated?.();
      // reject 후엔 그래프에서 노드도 사라지므로 패널 닫기
      setTimeout(onClose, 600);
    } catch (e) {
      setActionFeedback({ type: "err", msg: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusyAction(null);
    }
  };

  return (
    <div
      className="absolute left-0 right-0 bottom-0 bg-card border-t border-border shadow-2xl z-20 flex flex-col"
      style={{ height: PANEL_HEIGHT }}
    >
      {/* Header */}
      <div className="px-4 py-2 border-b border-border flex items-center gap-2 shrink-0">
        <span
          className="inline-block rounded-full"
          style={{ width: 9, height: 9, background: KIND_COLOR[node.kind] }}
        />
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
          {KIND_LABEL_KO[node.kind]}
        </span>
        <span className="font-semibold truncate flex-1" title={node.label}>
          {node.label}
        </span>
        {actionFeedback && (
          <span className={cn(
            "text-[11px] px-2 py-0.5 rounded flex items-center gap-1",
            actionFeedback.type === "ok"
              ? "bg-emerald-500/15 text-emerald-400"
              : "bg-destructive/15 text-destructive",
          )}>
            {actionFeedback.type === "ok" ? <Check className="w-3 h-3" /> : <AlertCircle className="w-3 h-3" />}
            {actionFeedback.msg}
          </span>
        )}
        <Button variant="ghost" size="sm" onClick={onTogglePin} className="h-7 w-7 p-0" title={pinned ? "고정 해제" : "고정"}>
          {pinned ? <PinOff className="w-3.5 h-3.5 text-primary" /> : <Pin className="w-3.5 h-3.5" />}
        </Button>
        <Button variant="ghost" size="sm" onClick={onClose} className="h-7 w-7 p-0" title="닫기">
          <X className="w-3.5 h-3.5" />
        </Button>
      </div>

      {/* Body — 2 column grid */}
      <div className="flex-1 overflow-y-auto px-4 py-3 grid grid-cols-2 gap-x-6 gap-y-2 text-[12px]">
        {/* Left col — meta */}
        <div className="space-y-1.5">
          <Field label="fqn"><code className="font-mono text-[10.5px] break-all">{node.id}</code></Field>
          {node.role && <Field label="role">{node.role}</Field>}
          {node.domain && <Field label="domain"><code className="font-mono text-[11px]">{node.domain}</code></Field>}
          {node.kind === "action" && typeof node.extra?.verification === "string" && (
            <Field label="verification">
              <span className={cn(
                "px-1.5 py-0.5 rounded text-[10px] font-mono",
                verifClass(String(node.extra.verification))
              )}>
                {String(node.extra.verification)}
              </span>
            </Field>
          )}
          {node.kind === "term" && node.extra?.is_root_entity ? (
            <Field label="root_entity"><span className="text-emerald-400">true</span></Field>
          ) : null}
          {node.kind === "term" && node.extra?.struct_like_hint ? (
            <Field label="struct_like">true</Field>
          ) : null}
          {node.kind === "code_type" && typeof node.extra?.kind_code === "string" && (
            <Field label="java kind">{String(node.extra.kind_code)}</Field>
          )}
          <Field label="confirmed">
            {node.confirmed
              ? <span className="text-emerald-400">✓ confirmed</span>
              : <span className="text-amber-400">queue 대기</span>}
          </Field>
        </div>

        {/* Right col — neighbors + edges */}
        <div className="space-y-1.5">
          <Field label="이웃 (1-hop)">
            <span className="flex gap-3 flex-wrap">
              {(["term", "code_type", "action", "domain"] as const).map((k) => (
                neighborCounts[k] > 0 ? (
                  <span key={k} className="flex items-center gap-1">
                    <span className="inline-block rounded-full" style={{ width: 6, height: 6, background: KIND_COLOR[k] }} />
                    <span className="font-mono">{neighborCounts[k]}</span>
                    <span className="text-muted-foreground text-[10px]">{KIND_LABEL_KO[k]}</span>
                  </span>
                ) : null
              ))}
              {(neighborCounts.term + neighborCounts.code_type + neighborCounts.action) === 0 && (
                <span className="text-muted-foreground text-[10px]">isolated</span>
              )}
            </span>
          </Field>
          <Field label="엣지 종류">
            <span className="flex gap-2 flex-wrap text-[10.5px]">
              {Object.entries(edgeKindCounts).length === 0
                ? <span className="text-muted-foreground">없음</span>
                : Object.entries(edgeKindCounts).map(([k, n]) => (
                    <span key={k} className="px-1.5 py-0.5 rounded bg-muted">
                      <span className={"font-mono " + edgeKindClass(k)}>{n}</span>
                      <span className="text-muted-foreground ml-1">{edgeKindShort(k)}</span>
                    </span>
                  ))
              }
            </span>
          </Field>
          {loading ? (
            <Field label="추가">
              <Loader2 className="w-3 h-3 animate-spin text-muted-foreground" />
            </Field>
          ) : detail && node.kind === "term" ? (
            <>
              {(detail as TermDTO).aliases.length > 0 && (
                <Field label="aliases">
                  <span className="text-[10.5px]">{(detail as TermDTO).aliases.slice(0, 4).join(", ")}</span>
                </Field>
              )}
              {(detail as TermDTO).description && (
                <Field label="설명">
                  <span className="text-[10.5px] text-muted-foreground line-clamp-2">{(detail as TermDTO).description}</span>
                </Field>
              )}
            </>
          ) : null}
          {!loading && detail && node.kind === "code_type" && (
            <Field label="methods">
              <span className="font-mono">{(detail as CodeTypeDTO).methods?.length ?? 0}</span>
              <span className="text-muted-foreground ml-1 text-[10px]">개</span>
            </Field>
          )}
          {!loading && detail && node.kind === "action" && (detail as ActionDTO).declared_on_term && (
            <Field label="on">
              <code className="font-mono text-[10.5px]">{(detail as ActionDTO).declared_on_term}</code>
            </Field>
          )}
        </div>
      </div>

      {/* Footer — quick actions */}
      <div className="px-4 py-2 border-t border-border flex items-center gap-2 shrink-0 bg-muted/20">
        <Button size="sm" variant="outline" onClick={() => onSetFocus(node.id)} className="h-7 gap-1.5">
          <Target className="w-3 h-3" /> 이 노드 중심
        </Button>
        <Button size="sm" variant="outline" onClick={openInDetail} className="h-7 gap-1.5">
          <ExternalLink className="w-3 h-3" /> Detail 모드 열기
        </Button>
        {(isUnconfirmedTerm || isUnconfirmedAction) && (
          <>
            <div className="h-5 w-px bg-border" />
            <Button
              size="sm" variant="outline" onClick={doConfirm} disabled={busyAction !== null}
              className="h-7 gap-1.5 text-emerald-400 hover:text-emerald-300"
            >
              {busyAction === "confirm" ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />}
              큐 확정
            </Button>
            <Button
              size="sm" variant="outline" onClick={doReject} disabled={busyAction !== null}
              className="h-7 gap-1.5 text-destructive hover:text-destructive"
            >
              {busyAction === "reject" ? <Loader2 className="w-3 h-3 animate-spin" /> : <XCircle className="w-3 h-3" />}
              거절
            </Button>
          </>
        )}
        <span className="ml-auto text-[10px] text-muted-foreground">
          {pinned ? "고정됨 — 다른 노드 클릭해도 유지" : "다른 노드 클릭 시 갈아치워짐"}
        </span>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground w-20 shrink-0">{label}</span>
      <span className="flex-1 min-w-0">{children}</span>
    </div>
  );
}

function verifClass(level: string): string {
  switch (level) {
    case "unmapped":         return "bg-destructive/15 text-destructive";
    case "draft":            return "bg-amber-500/15 text-amber-400";
    case "signature_locked": return "bg-amber-400/15 text-amber-300";
    case "body_anchored":    return "bg-primary/15 text-primary";
    case "sim_verified":     return "bg-emerald-500/15 text-emerald-400";
    case "pr_proven":        return "bg-emerald-500/25 text-emerald-300";
    default:                 return "bg-muted text-muted-foreground";
  }
}

function edgeKindShort(kind: string): string {
  switch (kind) {
    case "type_realization_primary": return "PRIMARY";
    case "type_realization_partial": return "PARTIAL";
    case "realization":              return "impl";
    case "extends":                  return "extends";
    case "implements":               return "implements";
    case "composition":              return "has";
    default:                         return kind;
  }
}

function edgeKindClass(kind: string): string {
  if (kind === "type_realization_primary") return "text-emerald-400";
  if (kind === "type_realization_partial") return "text-amber-400";
  if (kind === "realization")              return "text-orange-400";
  if (kind === "composition")              return "text-violet-400";
  return "text-muted-foreground";
}
