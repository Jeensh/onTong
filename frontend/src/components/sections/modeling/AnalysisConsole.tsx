"use client";

import React, { useState } from "react";
import {
  Search,
  Loader2,
  ArrowRight,
  AlertTriangle,
  Zap,
  Lightbulb,
} from "lucide-react";
import { engineQuery, type ImpactResult } from "@/lib/api/modeling";

interface AnalysisConsoleProps {
  repoId: string;
  onNavigateToSim?: (entityId: string) => void;
}

const EXAMPLE_QUERIES = [
  { text: "안전재고 계산 로직 변경", desc: "SafetyStockCalculator 영향 범위" },
  { text: "주문 서비스 수정", desc: "OrderService 의존성 추적" },
  { text: "생산 계획 변경", desc: "ProductionPlanner 영향 분석" },
  { text: "InventoryManager", desc: "재고 관리 코드 직접 검색" },
];

export function AnalysisConsole({ repoId, onNavigateToSim }: AnalysisConsoleProps) {
  const [query, setQuery] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<ImpactResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleAnalyze = async (input?: string) => {
    const q = (input ?? query).trim();
    if (!q) return;
    if (input) setQuery(input);

    setAnalyzing(true);
    setError(null);
    setResult(null);
    try {
      const res = await engineQuery(q, repoId);
      setResult(res);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.nativeEvent.isComposing) {
      handleAnalyze();
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-lg font-semibold mb-1">영향 분석</h2>
        <p className="text-sm text-muted-foreground">
          현업 요청이나 코드 이름을 입력하면, 변경 시 영향받는 비즈니스 프로세스를 자동으로 찾아줍니다.
        </p>
      </div>

      {/* Search bar */}
      <div className="relative">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder='현업 요청이나 코드를 입력하세요... 예: "안전재고 계산 로직 변경"'
              className="w-full pl-10 pr-4 py-3 text-sm bg-background border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
              disabled={analyzing}
            />
          </div>
          <button
            onClick={() => handleAnalyze()}
            disabled={analyzing || !query.trim()}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {analyzing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Search className="h-4 w-4" />
            )}
            분석
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-950/20 p-4 text-sm text-red-700 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Example queries (when no result) */}
      {!result && !analyzing && !error && (
        <div className="rounded-lg border border-border bg-muted/20 p-5">
          <div className="flex items-center gap-2 mb-3">
            <Lightbulb className="h-4 w-4 text-amber-500" />
            <span className="text-sm font-medium">예시 질의</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {EXAMPLE_QUERIES.map((eq) => (
              <button
                key={eq.text}
                onClick={() => handleAnalyze(eq.text)}
                className="text-left rounded-md border border-border bg-background px-3 py-2 hover:bg-muted/50 transition-colors"
              >
                <span className="text-sm font-medium text-foreground">{eq.text}</span>
                <span className="block text-xs text-muted-foreground mt-0.5">{eq.desc}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Loading */}
      {analyzing && (
        <div className="flex items-center justify-center py-12 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin mr-2" />
          <span className="text-sm">영향 범위를 분석하고 있습니다...</span>
        </div>
      )}

      {/* Results */}
      {result && !analyzing && (
        <div className="space-y-4">
          {/* Source resolution */}
          {result.resolved ? (
            <div className="rounded-lg border border-border bg-card p-4">
              <div className="text-xs text-muted-foreground mb-2">검색 대상</div>
              <div className="flex items-center gap-3">
                <div>
                  <span className="font-mono text-sm font-medium">
                    {result.source_code_entity?.split(".").pop()}
                  </span>
                  <span className="text-xs text-muted-foreground ml-2">
                    {result.source_code_entity}
                  </span>
                </div>
                {result.source_domain && (
                  <>
                    <ArrowRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    <span className="text-sm font-medium text-primary">
                      {result.source_domain}
                    </span>
                  </>
                )}
              </div>
            </div>
          ) : (
            <div className="rounded-lg border border-amber-300 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/20 p-4">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-500" />
                <span className="text-sm text-amber-700 dark:text-amber-400">
                  {result.message}
                </span>
              </div>
            </div>
          )}

          {/* Affected processes */}
          {result.affected_processes.length > 0 && (
            <div className="rounded-lg border border-border bg-card p-4">
              <div className="text-xs text-muted-foreground mb-3">
                영향받는 프로세스 ({result.affected_processes.length}개)
              </div>
              <div className="space-y-2">
                {result.affected_processes.map((ap, i) => (
                  <div
                    key={ap.domain_id}
                    className="flex items-center justify-between rounded-md bg-muted/30 px-3 py-2"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{ap.domain_name}</span>
                      <span className="text-xs text-muted-foreground">{ap.domain_id}</span>
                    </div>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      ap.distance === 0
                        ? "bg-primary/10 text-primary"
                        : "bg-muted text-muted-foreground"
                    }`}>
                      {ap.distance === 0 ? "직접 매핑" : `거리: ${ap.distance}`}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Simulation link */}
          {result.resolved && result.source_code_entity && onNavigateToSim && (
            <button
              onClick={() => onNavigateToSim(result.source_code_entity!)}
              className="inline-flex items-center gap-2 rounded-lg border border-primary/30 bg-primary/5 px-4 py-3 text-sm font-medium text-primary hover:bg-primary/10 transition-colors w-full justify-center"
            >
              <Zap className="h-4 w-4" />
              시뮬레이션 실행
              <ArrowRight className="h-4 w-4" />
            </button>
          )}

          {/* Unmapped entities */}
          {result.unmapped_entities.length > 0 && (
            <div className="rounded-lg border border-amber-300 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/20 p-4">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle className="h-4 w-4 text-amber-500" />
                <span className="text-sm font-medium text-amber-700 dark:text-amber-400">
                  미매핑 엔티티 {result.unmapped_entities.length}개
                </span>
              </div>
              <div className="space-y-1">
                {result.unmapped_entities.map((ue) => (
                  <div key={ue} className="text-xs font-mono text-amber-600 dark:text-amber-400">
                    {ue.split(".").pop()}
                    <span className="text-amber-400 dark:text-amber-600 ml-1">{ue}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Summary message */}
          <div className="text-xs text-muted-foreground text-center pt-2">
            {result.message}
          </div>
        </div>
      )}
    </div>
  );
}
