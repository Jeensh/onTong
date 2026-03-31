"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, FileText, RefreshCw, Loader2, XCircle, GitCompareArrows, CheckCircle2, Search } from "lucide-react";
import { useWorkspaceStore } from "@/lib/workspace/useWorkspaceStore";
import { toast } from "sonner";

interface DuplicatePair {
  file_a: string;
  file_b: string;
  similarity: number;
  meta_a: Record<string, string>;
  meta_b: Record<string, string>;
  resolved: boolean;
}

type FilterMode = "unresolved" | "resolved" | "all";

export function ConflictDashboard() {
  const [pairs, setPairs] = useState<DuplicatePair[]>([]);
  const [loading, setLoading] = useState(false);
  const [threshold, setThreshold] = useState(0.95);
  const [filterMode, setFilterMode] = useState<FilterMode>("unresolved");
  const [scanning, setScanning] = useState(false);
  const [scanProgress, setScanProgress] = useState({ progress: 0, total: 0 });
  const openTab = useWorkspaceStore((s) => s.openTab);
  const openCompareTab = useWorkspaceStore((s) => s.openCompareTab);

  const fetchDuplicates = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/conflict/duplicates?threshold=${threshold}&filter=${filterMode}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: DuplicatePair[] = await res.json();
      setPairs(data);
    } catch (e) {
      toast.error("충돌 감지 실패: " + (e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [threshold, filterMode]);

  useEffect(() => {
    fetchDuplicates();
  }, [fetchDuplicates]);

  // Listen for scan progress via SSE
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
            fetchDuplicates();
            toast.success("전체 스캔 완료");
          }
        }
      } catch {
        // ignore polling errors
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [scanning, scanProgress.total, fetchDuplicates]);

  const handleFullScan = useCallback(async () => {
    try {
      const res = await fetch(`/api/conflict/full-scan?threshold=${threshold}`, { method: "POST" });
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
  }, [threshold]);

  const handleDeprecate = useCallback(async (path: string) => {
    try {
      const res = await fetch(`/api/conflict/deprecate?path=${encodeURIComponent(path)}`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      toast.success(`${path} → deprecated`);
      fetchDuplicates();
    } catch (e) {
      toast.error("폐기 실패: " + (e as Error).message);
    }
  }, [fetchDuplicates]);

  return (
    <div className="h-full overflow-auto p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-500" />
            <h2 className="text-lg font-semibold">문서 충돌 감지</h2>
          </div>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
              유사도 임계값
              <input
                type="number"
                min={0.5}
                max={1.0}
                step={0.05}
                value={threshold}
                onChange={(e) => setThreshold(Number(e.target.value))}
                className="w-16 h-7 rounded border bg-background px-2 text-xs"
              />
            </label>
            <button
              onClick={fetchDuplicates}
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

        <p className="text-sm text-muted-foreground">
          임베딩 유사도 기반으로 내용이 비슷한 문서 쌍을 탐지합니다. 문서 저장 시 자동으로 감지됩니다.
        </p>

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
          <div className="text-center py-12 text-muted-foreground">
            <AlertTriangle className="h-8 w-8 mx-auto mb-2 opacity-30" />
            <p className="text-sm">유사 문서가 발견되지 않았습니다.</p>
            <p className="text-xs mt-1">문서 저장 시 자동으로 감지됩니다. 전체 스캔으로 일괄 검사할 수도 있습니다.</p>
          </div>
        )}

        {!loading && pairs.length > 0 && (
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">
              {pairs.length}개의 유사 문서 쌍 발견
            </p>
            {pairs.map((pair, idx) => (
              <div
                key={`${pair.file_a}-${pair.file_b}`}
                className="rounded-lg border bg-card p-4 space-y-3"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-amber-600 dark:text-amber-400">
                    #{idx + 1} — 유사도 {Math.round(pair.similarity * 100)}%
                    {pair.resolved && (
                      <span className="ml-2 inline-flex items-center gap-0.5 text-green-600 dark:text-green-400">
                        <CheckCircle2 className="h-3 w-3" />
                        해결됨
                      </span>
                    )}
                  </span>
                  <div className="w-24 h-1.5 rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-full rounded-full bg-amber-500"
                      style={{ width: `${pair.similarity * 100}%` }}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  {/* File A */}
                  <FileCard
                    path={pair.file_a}
                    meta={pair.meta_a}
                    onOpen={() => openTab(pair.file_a)}
                    onDeprecate={() => handleDeprecate(pair.file_a)}
                  />
                  {/* File B */}
                  <FileCard
                    path={pair.file_b}
                    meta={pair.meta_b}
                    onOpen={() => openTab(pair.file_b)}
                    onDeprecate={() => handleDeprecate(pair.file_b)}
                  />
                </div>
                <button
                  onClick={() => openCompareTab(pair.file_a, pair.file_b)}
                  className="inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs text-primary hover:bg-primary/5 transition-colors"
                >
                  <GitCompareArrows className="h-3 w-3" />
                  나란히 비교
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function FileCard({
  path,
  meta,
  onOpen,
  onDeprecate,
}: {
  path: string;
  meta: Record<string, string>;
  onOpen: () => void;
  onDeprecate: () => void;
}) {
  const isDeprecated = meta.status === "deprecated";

  return (
    <div className={`rounded border p-3 space-y-2 ${isDeprecated ? "opacity-50 border-red-300" : ""}`}>
      <button
        onClick={onOpen}
        className="flex items-center gap-1.5 text-xs font-medium text-primary hover:underline text-left"
      >
        <FileText className="h-3.5 w-3.5 flex-shrink-0" />
        <span className="truncate">{path.split("/").pop()}</span>
      </button>
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
        {meta.domain && <span>Domain: {meta.domain}</span>}
        {meta.updated_by && <span>수정자: {meta.updated_by}</span>}
        {meta.updated && <span>수정: {meta.updated}</span>}
        {meta.status && (
          <span className={`font-medium ${
            meta.status === "approved" ? "text-green-600" :
            meta.status === "deprecated" ? "text-red-500" :
            "text-muted-foreground"
          }`}>
            {meta.status}
          </span>
        )}
      </div>
      {!isDeprecated && (
        <button
          onClick={onDeprecate}
          className="inline-flex items-center gap-1 rounded text-[11px] text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950/30 px-1.5 py-0.5"
        >
          <XCircle className="h-3 w-3" />
          폐기(deprecated) 처리
        </button>
      )}
    </div>
  );
}
