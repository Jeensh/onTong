"use client";

import React, { useState } from "react";
import { Search, AlertTriangle, Loader2, ArrowRight } from "lucide-react";
import { analyzeImpact, type ImpactResult } from "@/lib/api/modeling";

export function ImpactQueryPanel({ repoId }: { repoId: string }) {
  const [term, setTerm] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<ImpactResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleAnalyze = async () => {
    if (!term.trim()) return;
    setAnalyzing(true);
    setError(null);
    setResult(null);
    try {
      const data = await analyzeImpact(term.trim(), repoId);
      setResult(data);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleAnalyze();
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold mb-1">영향분석</h2>
        <p className="text-sm text-muted-foreground">
          코드 엔티티나 도메인 프로세스를 검색하면, 변경 시 영향받는 범위를 보여줍니다.
          매핑된 코드-도메인 관계를 기반으로 영향 경로를 추적합니다.
        </p>
      </div>

      {/* Query input */}
      <div className="rounded-lg border border-border bg-card p-4 space-y-3">
        <label className="text-xs font-medium text-foreground">검색어</label>
        <div className="flex gap-2">
          <input
            type="text"
            value={term}
            onChange={(e) => setTerm(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="예: OrderService, InventoryManager, DemandPlanning"
            className="flex-1 px-3 py-1.5 text-sm bg-background border border-border rounded"
          />
          <button
            onClick={handleAnalyze}
            disabled={analyzing || !term.trim()}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {analyzing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
            분석
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-950/20 p-3 text-sm text-red-700 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="space-y-4">
          {/* Not resolved */}
          {!result.resolved && (
            <div className="rounded-lg border border-amber-300 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/20 p-4">
              <div className="flex items-center gap-2 mb-1">
                <AlertTriangle className="h-4 w-4 text-amber-500" />
                <span className="text-sm font-medium text-amber-700 dark:text-amber-400">검색 결과 없음</span>
              </div>
              <p className="text-xs text-muted-foreground">{result.message}</p>
            </div>
          )}

          {/* Source entity */}
          {result.resolved && (
            <div className="rounded-lg border border-border bg-card p-4 space-y-3">
              <p className="text-sm font-medium">검색 대상</p>
              <div className="grid grid-cols-3 gap-4 text-xs">
                <div>
                  <span className="text-muted-foreground">검색어: </span>
                  <span className="font-mono font-medium">{result.source_term}</span>
                </div>
                {result.source_code_entity && (
                  <div>
                    <span className="text-muted-foreground">코드 엔티티: </span>
                    <span className="font-mono">{result.source_code_entity}</span>
                  </div>
                )}
                {result.source_domain && (
                  <div>
                    <span className="text-muted-foreground">도메인: </span>
                    <span className="font-mono">{result.source_domain}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Affected processes */}
          {result.affected_processes.length > 0 && (
            <div className="rounded-lg border border-border bg-card">
              <div className="px-4 py-2.5 border-b border-border bg-muted/30 flex items-center justify-between">
                <span className="text-sm font-medium">영향받는 프로세스</span>
                <span className="text-xs text-muted-foreground">{result.affected_processes.length}개</span>
              </div>
              <div className="divide-y divide-border">
                {result.affected_processes.map((proc, i) => (
                  <div key={`${proc.domain_id}-${i}`} className="px-4 py-3 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">{proc.domain_name}</span>
                      <span className="text-[10px] text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
                        거리: {proc.distance}
                      </span>
                    </div>
                    {proc.path.length > 0 && (
                      <div className="flex items-center gap-1 flex-wrap text-xs text-muted-foreground">
                        {proc.path.map((step, j) => (
                          <React.Fragment key={j}>
                            {j > 0 && <ArrowRight className="h-3 w-3" />}
                            <span className="font-mono">{step}</span>
                          </React.Fragment>
                        ))}
                      </div>
                    )}
                    <span className="text-[10px] text-muted-foreground">{proc.domain_id}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Unmapped entities */}
          {result.unmapped_entities.length > 0 && (
            <div className="rounded-lg border border-amber-300 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/20 p-4 space-y-2">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-500" />
                <span className="text-sm font-medium text-amber-700 dark:text-amber-400">
                  미매핑 엔티티 ({result.unmapped_entities.length}개)
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {result.unmapped_entities.map((entity) => (
                  <span
                    key={entity}
                    className="text-xs font-mono bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300 px-2 py-0.5 rounded"
                  >
                    {entity}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Message */}
          {result.resolved && result.message && (
            <p className="text-xs text-muted-foreground">{result.message}</p>
          )}
        </div>
      )}

      {/* Empty state */}
      {!result && !error && !analyzing && (
        <div className="text-center py-12 text-muted-foreground space-y-2">
          <Search className="h-8 w-8 mx-auto mb-2 opacity-30" />
          <p className="text-sm">코드 엔티티 또는 도메인 프로세스를 검색하세요.</p>
          <p className="text-xs text-muted-foreground mt-1">
            검색 예시: <span className="font-mono">OrderService</span>, <span className="font-mono">InventoryManager</span>, <span className="font-mono">DemandPlanning</span>
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">
            해당 엔티티를 변경할 때 영향받는 도메인 프로세스와 연관 코드를 확인할 수 있습니다.
          </p>
        </div>
      )}
    </div>
  );
}
