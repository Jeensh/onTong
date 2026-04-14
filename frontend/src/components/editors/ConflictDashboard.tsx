"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  FileText,
  RefreshCw,
  Loader2,
  Search,
  GitCompareArrows,
  CheckCircle2,
  Link2,
  History,
  Merge,
  X,
  Sparkles,
  ChevronDown,
  Info,
  ChevronRight,
  Undo2,
} from "lucide-react";
import { useWorkspaceStore } from "@/lib/workspace/useWorkspaceStore";
import { toast } from "sonner";
import type { TypedConflict, ConflictType, ConflictResolution } from "@/types/wiki";

type FilterMode = "unresolved" | "resolved" | "all";

const PAGE_SIZE = 20;

const TYPE_CONFIG: Record<ConflictType, { label: string; color: string; bg: string; desc: string }> = {
  factual_contradiction: {
    label: "사실 불일치",
    color: "text-red-600 dark:text-red-400",
    bg: "bg-red-100 dark:bg-red-950/40",
    desc: "같은 주제에 대해 서로 다른 사실을 말하고 있습니다. 하나를 수정하거나 버전 체인으로 연결하세요.",
  },
  scope_overlap: {
    label: "범위 중복",
    color: "text-amber-600 dark:text-amber-400",
    bg: "bg-amber-100 dark:bg-amber-950/40",
    desc: "비슷한 영역을 다루지만 보완 관계일 수 있습니다. 상호 링크로 연결하면 독자에게 도움이 됩니다.",
  },
  temporal: {
    label: "시간 차이",
    color: "text-blue-600 dark:text-blue-400",
    bg: "bg-blue-100 dark:bg-blue-950/40",
    desc: "하나가 다른 문서의 이전/이후 버전입니다. 버전 체인으로 최신 문서를 지정하세요.",
  },
  none: {
    label: "무관",
    color: "text-muted-foreground",
    bg: "bg-muted",
    desc: "내용상 충돌이 없습니다. 무시해도 됩니다.",
  },
};

const SEVERITY_DOT: Record<string, string> = {
  high: "bg-red-500",
  medium: "bg-amber-500",
  low: "bg-gray-400",
};

const RESOLVE_ACTIONS: { key: ConflictResolution; label: string; icon: typeof Link2; desc: string; detail: string }[] = [
  {
    key: "scope_clarify",
    label: "범위 명시",
    icon: Link2,
    desc: "상호 related 링크 추가",
    detail: "양쪽 문서에 서로를 '관련 문서'로 등록합니다. 범위가 다른 보완 관계일 때 사용하세요.",
  },
  {
    key: "version_chain",
    label: "버전 체인",
    icon: History,
    desc: "구버전 → 신버전 연결",
    detail: "왼쪽 문서를 '폐기(deprecated)'로 설정하고, 오른쪽 문서를 최신 버전으로 연결합니다.",
  },
  {
    key: "merge",
    label: "병합 제안",
    icon: Merge,
    desc: "두 문서를 하나로 통합",
    detail: "두 문서의 내용을 하나로 합칩니다. (추후 AI 병합 초안 지원 예정)",
  },
  {
    key: "dismiss",
    label: "무시",
    icon: X,
    desc: "오탐으로 표시",
    detail: "실제로 충돌이 아닌 경우 무시 처리합니다. 다시 나타나지 않습니다.",
  },
];

interface PaginatedResponse {
  items: TypedConflict[];
  total: number;
  limit: number;
  offset: number;
}

export function ConflictDashboard() {
  const [pairs, setPairs] = useState<TypedConflict[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(false);
  const [filterMode, setFilterMode] = useState<FilterMode>("unresolved");
  const [scanning, setScanning] = useState(false);
  const [scanProgress, setScanProgress] = useState({ progress: 0, total: 0 });
  const [analyzing, setAnalyzing] = useState<string | null>(null);
  const [showGuide, setShowGuide] = useState(false);
  const openTab = useWorkspaceStore((s) => s.openTab);
  const openCompareTab = useWorkspaceStore((s) => s.openCompareTab);
  const refreshTree = useWorkspaceStore((s) => s.refreshTree);

  const fetchPairs = useCallback(async () => {
    setLoading(true);
    try {
      const offset = page * PAGE_SIZE;
      const res = await fetch(`/api/conflict/typed?filter=${filterMode}&limit=${PAGE_SIZE}&offset=${offset}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: PaginatedResponse = await res.json();
      setPairs(data.items);
      setTotal(data.total);
    } catch (e) {
      toast.error("관련 문서 로딩 실패: " + (e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [filterMode, page]);

  useEffect(() => {
    fetchPairs();
  }, [fetchPairs]);

  // Reset page on filter change
  useEffect(() => {
    setPage(0);
  }, [filterMode]);

  // Scan progress polling
  useEffect(() => {
    if (!scanning) return;
    const interval = setInterval(async () => {
      try {
        const res = await fetch("/api/conflict/scan-status");
        if (res.ok) {
          const state = await res.json();
          setScanProgress({ progress: state.progress, total: state.total });
          if (!state.running && scanProgress.total > 0) {
            setScanning(false);
            setScanProgress({ progress: 0, total: 0 });
            fetchPairs();
            toast.success("전체 스캔 완료");
          }
        }
      } catch {
        // ignore
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [scanning, scanProgress.total, fetchPairs]);

  const handleFullScan = useCallback(async () => {
    try {
      const res = await fetch("/api/conflict/full-scan", { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (data.status === "already_running") {
        toast.info("전체 스캔이 이미 진행 중입니다.");
        setScanProgress({ progress: data.progress, total: data.total });
      } else {
        toast.info("전체 스캔을 시작합니다...");
      }
      setScanning(true);
    } catch (e) {
      toast.error("전체 스캔 실패: " + (e as Error).message);
    }
  }, []);

  const handleResolve = useCallback(
    async (pair: TypedConflict, action: ConflictResolution) => {
      try {
        const res = await fetch("/api/conflict/resolve", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            file_a: pair.file_a,
            file_b: pair.file_b,
            action,
            resolved_by: "",
          }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (data.error) {
          toast.error(data.error);
          return;
        }
        toast.success(`해결 완료: ${RESOLVE_ACTIONS.find((a) => a.key === action)?.label}`);
        fetchPairs();
      } catch (e) {
        toast.error("해결 실패: " + (e as Error).message);
      }
    },
    [fetchPairs],
  );

  const handleAnalyze = useCallback(
    async (pair: TypedConflict) => {
      const key = `${pair.file_a}|${pair.file_b}`;
      setAnalyzing(key);
      try {
        const res = await fetch(
          `/api/conflict/analyze-pair?file_a=${encodeURIComponent(pair.file_a)}&file_b=${encodeURIComponent(pair.file_b)}`,
          { method: "POST" },
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (data.error) {
          toast.error(data.error);
          return;
        }
        toast.success("분석 완료");
        fetchPairs();
      } catch (e) {
        toast.error("분석 실패: " + (e as Error).message);
      } finally {
        setAnalyzing(null);
      }
    },
    [fetchPairs],
  );

  const handleUndeprecate = useCallback(
    async (path: string) => {
      try {
        const res = await fetch(`/api/conflict/undeprecate?path=${encodeURIComponent(path)}`, { method: "POST" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (data.error) { toast.error(data.error); return; }
        toast.success("폐기 되돌리기 완료", {
          description: `${path.split("/").pop()} → ${data.new_status}`,
        });
        window.dispatchEvent(new CustomEvent("wiki:lineage-changed", { detail: { path } }));
        refreshTree();
        fetchPairs();
      } catch (e) {
        toast.error("되돌리기 실패", { description: (e as Error).message });
      }
    },
    [fetchPairs],
  );

  const analyzedCount = pairs.filter((p) => p.analyzed_at > 0).length;
  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="h-full overflow-auto p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-500" />
            <h2 className="text-lg font-semibold">관련 문서 관리</h2>
            {total > 0 && (
              <span className="text-xs bg-amber-100 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 px-2 py-0.5 rounded-full">
                {total}건
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={fetchPairs}
              disabled={loading}
              className="inline-flex items-center gap-1 rounded-md bg-primary px-3 py-1.5 text-xs text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
              새로고침
            </button>
            <button
              onClick={handleFullScan}
              disabled={scanning}
              className="inline-flex items-center gap-1 rounded-md border border-amber-500 text-amber-600 dark:text-amber-400 px-3 py-1.5 text-xs hover:bg-amber-50 dark:hover:bg-amber-950/30 disabled:opacity-50"
            >
              {scanning ? <Loader2 className="h-3 w-3 animate-spin" /> : <Search className="h-3 w-3" />}
              전체 스캔
            </button>
          </div>
        </div>

        {/* Description */}
        <div className="text-sm text-muted-foreground space-y-2">
          <p>
            문서 저장 시 자동으로 유사한 문서를 감지합니다. AI 분석을 실행하면 충돌 유형과 해결 방법을 추천합니다.
            {analyzedCount > 0 && (
              <span className="ml-1 text-xs">({analyzedCount}/{pairs.length}건 AI 분석 완료)</span>
            )}
          </p>
          <button
            onClick={() => setShowGuide(!showGuide)}
            className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
          >
            <Info className="h-3 w-3" />
            {showGuide ? "사용 가이드 닫기" : "사용 가이드 보기"}
            <ChevronRight className={`h-3 w-3 transition-transform ${showGuide ? "rotate-90" : ""}`} />
          </button>
        </div>

        {/* Guide panel */}
        {showGuide && (
          <div className="rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-950/20 p-4 space-y-3 text-xs leading-relaxed">
            <p className="font-semibold text-blue-700 dark:text-blue-300">처리 순서</p>
            <ol className="list-decimal list-inside space-y-1 text-muted-foreground">
              <li><strong>전체 스캔</strong>으로 위키의 모든 문서를 검사합니다. (첫 사용 시 권장)</li>
              <li>감지된 문서 쌍에서 <strong>AI 분석</strong> 버튼을 눌러 충돌 유형을 파악합니다.</li>
              <li>AI의 추천을 참고하여 적절한 <strong>해결 액션</strong>을 선택합니다.</li>
            </ol>
            <div className="border-t border-blue-200 dark:border-blue-800 pt-3 space-y-2">
              <p className="font-semibold text-blue-700 dark:text-blue-300">유형별 의미</p>
              {(Object.entries(TYPE_CONFIG) as [ConflictType, typeof TYPE_CONFIG[ConflictType]][]).map(([key, conf]) => (
                <div key={key} className="flex items-start gap-2">
                  <span className={`shrink-0 inline-block px-1.5 py-0.5 rounded text-[10px] font-medium ${conf.color} ${conf.bg}`}>
                    {conf.label}
                  </span>
                  <span className="text-muted-foreground">{conf.desc}</span>
                </div>
              ))}
            </div>
            <div className="border-t border-blue-200 dark:border-blue-800 pt-3 space-y-2">
              <p className="font-semibold text-blue-700 dark:text-blue-300">해결 액션</p>
              {RESOLVE_ACTIONS.map((action) => (
                <div key={action.key} className="flex items-start gap-2">
                  <span className="shrink-0 inline-flex items-center gap-0.5 text-[10px] font-medium text-foreground">
                    <action.icon className="h-3 w-3" />
                    {action.label}
                  </span>
                  <span className="text-muted-foreground">{action.detail}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Scan progress */}
        {scanning && scanProgress.total > 0 && (
          <div className="space-y-1">
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>전체 스캔 진행 중...</span>
              <span>{scanProgress.progress} / {scanProgress.total}</span>
            </div>
            <div className="h-2 rounded-full bg-muted overflow-hidden">
              <div
                className="h-full rounded-full bg-amber-500 transition-all"
                style={{ width: `${(scanProgress.progress / scanProgress.total) * 100}%` }}
              />
            </div>
          </div>
        )}

        {/* Filter tabs */}
        <div className="flex gap-1 border-b">
          {([
            { key: "unresolved" as FilterMode, label: "미해결" },
            { key: "resolved" as FilterMode, label: "해결됨" },
            { key: "all" as FilterMode, label: "전체" },
          ]).map((tab) => (
            <button
              key={tab.key}
              onClick={() => setFilterMode(tab.key)}
              className={`px-3 py-1.5 text-xs font-medium border-b-2 transition-colors ${
                filterMode === tab.key
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Results */}
        {loading && (
          <div className="flex items-center justify-center py-12 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin mr-2" />
            불러오는 중...
          </div>
        )}

        {!loading && pairs.length === 0 && (
          <div className="text-center py-12 text-muted-foreground space-y-2">
            <AlertTriangle className="h-8 w-8 mx-auto mb-2 opacity-30" />
            <p className="text-sm">관련 문서가 발견되지 않았습니다.</p>
            <p className="text-xs">
              문서 저장 시 자동으로 감지됩니다. 위의 <strong>전체 스캔</strong> 버튼으로 위키 전체를 한 번에 검사할 수 있습니다.
            </p>
            {filterMode === "resolved" && (
              <p className="text-xs">해결된 문서 쌍이 없습니다. "미해결" 탭에서 문서를 처리하면 여기에 표시됩니다.</p>
            )}
          </div>
        )}

        {!loading && pairs.length > 0 && (
          <div className="space-y-3">
            {pairs.map((pair) => {
              const pairKey = `${pair.file_a}|${pair.file_b}`;
              const isAnalyzed = pair.analyzed_at > 0;
              const typeConf = TYPE_CONFIG[pair.conflict_type] || TYPE_CONFIG.none;
              const isAnalyzing = analyzing === pairKey;

              return (
                <div
                  key={pairKey}
                  className={`rounded-lg border bg-card p-4 space-y-3 ${
                    pair.resolved ? "opacity-60" : ""
                  }`}
                >
                  {/* Top row: type badge + severity + similarity */}
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {isAnalyzed ? (
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium ${typeConf.color} ${typeConf.bg}`}
                          title={typeConf.desc}
                        >
                          <span className={`w-1.5 h-1.5 rounded-full ${SEVERITY_DOT[pair.severity] || SEVERITY_DOT.low}`} />
                          {typeConf.label}
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium text-muted-foreground bg-muted">
                          미분석 — AI 분석을 실행하세요
                        </span>
                      )}
                      <span className="text-[11px] text-muted-foreground">
                        유사도 {Math.round(pair.similarity * 100)}%
                      </span>
                      {pair.resolved && (
                        <span className="inline-flex items-center gap-0.5 text-[11px] text-green-600 dark:text-green-400">
                          <CheckCircle2 className="h-3 w-3" />
                          해결됨{pair.resolved_action && ` (${pair.resolved_action})`}
                        </span>
                      )}
                    </div>
                    <div className="w-20 h-1.5 rounded-full bg-muted overflow-hidden">
                      <div
                        className="h-full rounded-full bg-amber-500"
                        style={{ width: `${pair.similarity * 100}%` }}
                      />
                    </div>
                  </div>

                  {/* Type explanation (if analyzed) */}
                  {isAnalyzed && pair.conflict_type !== "none" && (
                    <p className="text-[11px] text-muted-foreground/70 italic">
                      {typeConf.desc}
                    </p>
                  )}

                  {/* Summary (if analyzed) */}
                  {isAnalyzed && pair.summary_ko && (
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      {pair.summary_ko}
                    </p>
                  )}

                  {/* Document pair */}
                  <div className="grid grid-cols-2 gap-3">
                    <DocCard
                      path={pair.file_a}
                      claim={isAnalyzed ? pair.claim_a : ""}
                      onOpen={() => openTab(pair.file_a)}
                    />
                    <DocCard
                      path={pair.file_b}
                      claim={isAnalyzed ? pair.claim_b : ""}
                      onOpen={() => openTab(pair.file_b)}
                    />
                  </div>

                  {/* Resolution detail */}
                  {isAnalyzed && pair.resolution_detail && !pair.resolved && (
                    <div className="text-xs text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/20 rounded px-3 py-2">
                      <strong>AI 추천:</strong> {pair.resolution_detail}
                    </div>
                  )}

                  {/* Action buttons */}
                  <div className="flex items-center gap-2 flex-wrap">
                    <button
                      onClick={() => openCompareTab(pair.file_a, pair.file_b)}
                      className="inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs text-primary hover:bg-primary/5 transition-colors"
                    >
                      <GitCompareArrows className="h-3 w-3" />
                      비교
                    </button>

                    {!isAnalyzed && !pair.resolved && (
                      <button
                        onClick={() => handleAnalyze(pair)}
                        disabled={isAnalyzing}
                        className="inline-flex items-center gap-1 rounded-md border border-purple-300 dark:border-purple-700 text-purple-600 dark:text-purple-400 px-2.5 py-1 text-xs hover:bg-purple-50 dark:hover:bg-purple-950/30 disabled:opacity-50"
                      >
                        {isAnalyzing ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          <Sparkles className="h-3 w-3" />
                        )}
                        AI 분석
                      </button>
                    )}

                    {!pair.resolved && (
                      <>
                        {RESOLVE_ACTIONS.map((action) => (
                          <button
                            key={action.key}
                            onClick={() => handleResolve(pair, action.key)}
                            title={action.detail}
                            className="inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
                          >
                            <action.icon className="h-3 w-3" />
                            {action.label}
                          </button>
                        ))}
                      </>
                    )}

                    {pair.resolved && (pair.resolved_action === "version_chain" || pair.resolved_action === "auto_deprecated") && (
                      <button
                        onClick={() => handleUndeprecate(pair.file_a)}
                        title="폐기된 문서를 원래 상태로 복원합니다"
                        className="inline-flex items-center gap-1 rounded-md border border-amber-300 dark:border-amber-700 text-amber-600 dark:text-amber-400 px-2.5 py-1 text-xs hover:bg-amber-50 dark:hover:bg-amber-950/30 transition-colors"
                      >
                        <Undo2 className="h-3 w-3" />
                        폐기 되돌리기
                      </button>
                    )}
                  </div>
                </div>
              );
            })}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between pt-4 border-t">
                <p className="text-xs text-muted-foreground">
                  전체 {total}건 중 {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)}건
                </p>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setPage((p) => Math.max(0, p - 1))}
                    disabled={page === 0}
                    className="px-2 py-1 text-xs rounded border disabled:opacity-30 hover:bg-accent"
                  >
                    이전
                  </button>
                  <span className="text-xs text-muted-foreground px-2">
                    {page + 1} / {totalPages}
                  </span>
                  <button
                    onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                    disabled={page >= totalPages - 1}
                    className="px-2 py-1 text-xs rounded border disabled:opacity-30 hover:bg-accent"
                  >
                    다음
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function DocCard({
  path,
  claim,
  onOpen,
}: {
  path: string;
  claim: string;
  onOpen: () => void;
}) {
  const filename = path.split("/").pop() || path;

  return (
    <div className="rounded border p-3 space-y-1.5">
      <button
        onClick={onOpen}
        className="flex items-center gap-1.5 text-xs font-medium text-primary hover:underline text-left"
      >
        <FileText className="h-3.5 w-3.5 flex-shrink-0" />
        <span className="truncate">{filename}</span>
      </button>
      <p className="text-[10px] text-muted-foreground truncate" title={path}>
        {path}
      </p>
      {claim && (
        <p className="text-[11px] text-muted-foreground italic leading-relaxed line-clamp-2">
          &ldquo;{claim}&rdquo;
        </p>
      )}
    </div>
  );
}
