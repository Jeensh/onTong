"use client";

/**
 * Coverage mode — graph redesign Option 3 의 "daily entry point".
 *
 * 도메인 grid heatmap + lens 토글 (draft / orphan / recent) + cell click → priority panel.
 * entity click → useWorkbench.jumpToImpact(...) 로 Impact mode 전환.
 *
 * Backend: GET /graph/coverage + /graph/coverage/{domain}/priority.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2, RotateCw, ChevronRight, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  ontologyApi,
  type CoverageResponseDTO,
  type DomainCellDTO,
  type PriorityEntityDTO,
  type PriorityResponseDTO,
} from "@/lib/api/ontology";
import {
  useWorkbench,
  type CoverageLens,
  type ImpactFocusKind,
} from "./store";

const ALL_LENSES: { id: CoverageLens; label: string; tone: string }[] = [
  { id: "draft",  label: "Draft",  tone: "bg-amber-100 text-amber-800 border-amber-300" },
  { id: "orphan", label: "Orphan", tone: "bg-rose-100 text-rose-800 border-rose-300" },
  { id: "recent", label: "Recent", tone: "bg-sky-100 text-sky-800 border-sky-300" },
];

export function CoverageView({ repoId }: { repoId: string }) {
  const lenses = useWorkbench((s) => s.coverageLenses);
  const toggleLens = useWorkbench((s) => s.toggleCoverageLens);
  const recentDays = useWorkbench((s) => s.coverageRecentDays);
  const setRecentDays = useWorkbench((s) => s.setCoverageRecentDays);
  const expandedDomain = useWorkbench((s) => s.coverageExpandedDomain);
  const setExpandedDomain = useWorkbench((s) => s.setCoverageExpandedDomain);
  const jumpToImpact = useWorkbench((s) => s.jumpToImpact);

  const [data, setData] = useState<CoverageResponseDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [reloadTick, setReloadTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr(null);
    ontologyApi
      .getCoverage(repoId, recentDays)
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
  }, [repoId, recentDays, reloadTick]);

  const stalledSet = useMemo(
    () => new Set(data?.summary.stalled_domains ?? []),
    [data?.summary.stalled_domains],
  );

  // 정렬: confirmed_ratio ASC (덜 끝난 게 위로), 같으면 total DESC
  const sortedDomains = useMemo(() => {
    if (!data) return [] as DomainCellDTO[];
    return [...data.domains].sort((a, b) => {
      if (a.confirmed_ratio !== b.confirmed_ratio) return a.confirmed_ratio - b.confirmed_ratio;
      return b.total - a.total;
    });
  }, [data]);

  const onCellClick = useCallback(
    (domain: string) => {
      setExpandedDomain(expandedDomain === domain ? null : domain);
    },
    [expandedDomain, setExpandedDomain],
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
        <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Coverage 로딩중…
      </div>
    );
  }
  if (err) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-sm text-rose-700 gap-2">
        <span>Coverage 로드 실패: {err}</span>
        <Button size="sm" variant="outline" onClick={() => setReloadTick((t) => t + 1)}>
          <RotateCw className="w-3 h-3 mr-1" /> 재시도
        </Button>
      </div>
    );
  }
  if (!data) return null;

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="px-3 py-2 bg-card border-b border-border flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-1.5 text-[11px]">
          <span className="text-muted-foreground">Lens</span>
          {ALL_LENSES.map((l) => {
            const on = lenses.includes(l.id);
            return (
              <button
                key={l.id}
                onClick={() => toggleLens(l.id)}
                className={cn(
                  "px-2 py-0.5 rounded border text-[11px] transition-all",
                  on ? l.tone : "bg-muted text-muted-foreground border-transparent hover:bg-muted/70",
                )}
              >
                {on ? "☑" : "☐"} {l.label}
              </button>
            );
          })}
        </div>
        {lenses.includes("recent") && (
          <label className="flex items-center gap-1 text-[11px] text-muted-foreground">
            since
            <select
              value={recentDays}
              onChange={(e) => setRecentDays(Number(e.target.value))}
              className="h-6 text-[11px] border rounded px-1 bg-background"
            >
              <option value={1}>1d</option>
              <option value={3}>3d</option>
              <option value={7}>7d</option>
              <option value={14}>14d</option>
              <option value={30}>30d</option>
            </select>
          </label>
        )}
        <div className="ml-auto flex items-center gap-3 text-[11px] text-muted-foreground">
          <span>전체 {data.summary.total} entity</span>
          <span>완료율 {(data.summary.confirmed_ratio * 100).toFixed(1)}%</span>
          {data.summary.stalled_domains.length > 0 && (
            <span className="text-rose-600">
              stalled {data.summary.stalled_domains.length}
            </span>
          )}
          <Button size="sm" variant="outline" className="h-6 px-2" onClick={() => setReloadTick((t) => t + 1)}>
            <RotateCw className="w-3 h-3" />
          </Button>
        </div>
      </div>

      {/* Heatmap grid */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {sortedDomains.length === 0 ? (
          <div className="text-center text-sm text-muted-foreground py-12">
            도메인 데이터가 없습니다. Repo Import 후 다시 확인해주세요.
          </div>
        ) : (
          sortedDomains.map((cell) => (
            <DomainCell
              key={cell.domain}
              cell={cell}
              isStalled={stalledSet.has(cell.domain)}
              expanded={expandedDomain === cell.domain}
              onToggle={() => onCellClick(cell.domain)}
              lenses={lenses}
              repoId={repoId}
              recentDays={recentDays}
              onEntityClick={jumpToImpact}
            />
          ))
        )}
      </div>
    </div>
  );
}

function DomainCell({
  cell,
  isStalled,
  expanded,
  onToggle,
  lenses,
  repoId,
  recentDays,
  onEntityClick,
}: {
  cell: DomainCellDTO;
  isStalled: boolean;
  expanded: boolean;
  onToggle: () => void;
  lenses: CoverageLens[];
  repoId: string;
  recentDays: number;
  onEntityClick: (fqn: string, kind: ImpactFocusKind) => void;
}) {
  const ratio = cell.confirmed_ratio;
  // 색조: 80%↑ green / 50~80% amber / <50% rose
  const tone =
    ratio >= 0.8
      ? "bg-emerald-50 border-emerald-300"
      : ratio >= 0.5
      ? "bg-amber-50 border-amber-300"
      : "bg-rose-50 border-rose-300";
  const barTone =
    ratio >= 0.8 ? "bg-emerald-500" : ratio >= 0.5 ? "bg-amber-500" : "bg-rose-500";

  return (
    <div className={cn("border rounded-md", tone)}>
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-white/60"
      >
        <ChevronRight
          className={cn(
            "w-3.5 h-3.5 text-muted-foreground transition-transform shrink-0",
            expanded && "rotate-90",
          )}
        />
        <span className="font-semibold text-[13px] min-w-0 truncate flex-1">
          {cell.domain}
        </span>
        {isStalled && (
          <span className="text-[10px] px-1.5 py-0.5 bg-rose-200 text-rose-800 rounded shrink-0">
            stalled
          </span>
        )}
        <div className="flex items-center gap-3 shrink-0 text-[11px]">
          <span className="text-muted-foreground">총 {cell.total}</span>
          <div className="flex items-center gap-1">
            <div className="w-24 h-2 bg-white/70 rounded overflow-hidden">
              <div
                className={cn("h-full transition-all", barTone)}
                style={{ width: `${Math.round(ratio * 100)}%` }}
              />
            </div>
            <span className="font-mono w-9 text-right">
              {Math.round(ratio * 100)}%
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            {cell.draft > 0 && (
              <span className="px-1.5 py-0.5 rounded bg-amber-100 text-amber-800">
                D {cell.draft}
              </span>
            )}
            {cell.orphan_count > 0 && (
              <span className="px-1.5 py-0.5 rounded bg-rose-100 text-rose-800">
                O {cell.orphan_count}
              </span>
            )}
            {cell.recent_count > 0 && (
              <span className="px-1.5 py-0.5 rounded bg-sky-100 text-sky-800">
                R {cell.recent_count}
              </span>
            )}
          </div>
        </div>
      </button>
      {expanded && (
        <PriorityPanel
          repoId={repoId}
          domain={cell.domain}
          lenses={lenses}
          recentDays={recentDays}
          onEntityClick={onEntityClick}
        />
      )}
    </div>
  );
}

function PriorityPanel({
  repoId,
  domain,
  lenses,
  recentDays,
  onEntityClick,
}: {
  repoId: string;
  domain: string;
  lenses: CoverageLens[];
  recentDays: number;
  onEntityClick: (fqn: string, kind: ImpactFocusKind) => void;
}) {
  const [data, setData] = useState<PriorityResponseDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr(null);
    ontologyApi
      .getCoveragePriority(repoId, domain, {
        lens: lenses.join(","),
        limit: 50,
        recent_days: recentDays,
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
  }, [repoId, domain, lenses, recentDays]);

  if (loading) {
    return (
      <div className="px-6 py-3 text-[11px] text-muted-foreground flex items-center gap-2 border-t">
        <Loader2 className="w-3 h-3 animate-spin" /> 우선 처리 대상 로드중…
      </div>
    );
  }
  if (err) {
    return (
      <div className="px-6 py-3 text-[11px] text-rose-700 border-t">
        로드 실패: {err}
      </div>
    );
  }
  if (!data || data.entities.length === 0) {
    return (
      <div className="px-6 py-3 text-[11px] text-muted-foreground border-t">
        선택된 lens 에 해당하는 항목이 없습니다.
      </div>
    );
  }

  return (
    <div className="border-t bg-white/40 px-3 py-2">
      <div className="text-[10px] text-muted-foreground mb-1.5">
        우선 처리 대상 ({data.total_match}개 · 상위 {data.entities.length})
      </div>
      <ul className="space-y-1">
        {data.entities.map((e) => (
          <PriorityEntityRow key={`${e.kind}|${e.fqn}`} e={e} onClick={onEntityClick} />
        ))}
      </ul>
    </div>
  );
}

function PriorityEntityRow({
  e,
  onClick,
}: {
  e: PriorityEntityDTO;
  onClick: (fqn: string, kind: ImpactFocusKind) => void;
}) {
  const focusKind: ImpactFocusKind =
    e.kind === "action" ? "action" : e.kind === "term" ? "term" : "code_type";
  return (
    <li className="flex items-center gap-2 px-2 py-1 rounded hover:bg-white transition-colors group">
      <span
        className={cn(
          "text-[10px] px-1.5 py-0.5 rounded shrink-0 font-mono",
          e.kind === "action"
            ? "bg-violet-100 text-violet-800"
            : e.kind === "term"
            ? "bg-emerald-100 text-emerald-800"
            : "bg-slate-100 text-slate-700",
        )}
      >
        {e.kind === "code_type" ? "type" : e.kind}
      </span>
      <span className="font-mono text-[11px] truncate flex-1 min-w-0" title={e.fqn}>
        {e.label || e.fqn}
      </span>
      <div className="flex items-center gap-1 shrink-0">
        {e.reasons.map((r) => (
          <span
            key={r}
            className={cn(
              "text-[9px] px-1 rounded",
              r === "draft" && "bg-amber-100 text-amber-800",
              r === "orphan" && "bg-rose-100 text-rose-800",
              r === "recent" && "bg-sky-100 text-sky-800",
              r === "low_verification" && "bg-orange-100 text-orange-800",
              r === "draft_user_change" && "bg-violet-100 text-violet-800",
            )}
          >
            {r}
          </span>
        ))}
      </div>
      <span className="font-mono text-[10px] text-muted-foreground w-8 text-right shrink-0">
        {e.priority_score.toFixed(1)}
      </span>
      <Button
        size="sm"
        variant="ghost"
        className="h-6 px-1.5 text-[10px] gap-1 opacity-0 group-hover:opacity-100 shrink-0"
        onClick={() => onClick(e.fqn, focusKind)}
        title="Impact mode 로 이동"
      >
        Impact <ArrowRight className="w-3 h-3" />
      </Button>
    </li>
  );
}
