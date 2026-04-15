"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Code, FolderTree, Box, Braces, Loader2, Search, ChevronDown, ChevronRight, Wrench } from "lucide-react";
import { parseRepo, getCodeGraph, type CodeEntity, type ParseResponse } from "@/lib/api/modeling";

const KIND_ICON: Record<string, React.ReactNode> = {
  package: <FolderTree className="h-3.5 w-3.5 text-yellow-500" />,
  class: <Box className="h-3.5 w-3.5 text-blue-500" />,
  method: <Braces className="h-3.5 w-3.5 text-green-500" />,
  field: <Code className="h-3.5 w-3.5 text-muted-foreground" />,
  constructor: <Wrench className="h-3.5 w-3.5 text-orange-500" />,
};

const KIND_ORDER = ["package", "class", "method", "field", "constructor"];
const PAGE_SIZE = 20;

function getIcon(kind: string) {
  return Object.hasOwn(KIND_ICON, kind) ? KIND_ICON[kind] : <Code className="h-3.5 w-3.5 text-muted-foreground" />;
}

export function CodeGraphViewer({ repoId }: { repoId: string }) {
  const [repoUrl, setRepoUrl] = useState("");
  const [parsing, setParsing] = useState(false);
  const [parseResult, setParseResult] = useState<ParseResponse | null>(null);
  const [entities, setEntities] = useState<CodeEntity[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // UX state
  const [searchQuery, setSearchQuery] = useState("");
  const [kindFilter, setKindFilter] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>(Object.create(null));
  const [expanded, setExpanded] = useState<Record<string, boolean>>(Object.create(null));

  const fetchGraph = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getCodeGraph(repoId);
      setEntities(data.entities);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [repoId]);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  // Reset UX state when entities change
  useEffect(() => {
    const init = Object.create(null) as Record<string, boolean>;
    // Default: only "class" and "package" expanded
    for (const kind of KIND_ORDER) {
      init[kind] = kind !== "class" && kind !== "package";
    }
    setCollapsed(init);
    setExpanded(Object.create(null));
  }, [entities]);

  const handleParse = async () => {
    if (!repoUrl.trim()) return;
    setParsing(true);
    setError(null);
    try {
      const result = await parseRepo({ repo_url: repoUrl.trim(), repo_id: repoId });
      setParseResult(result);
      await fetchGraph();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setParsing(false);
    }
  };

  // Filter + group
  const filtered = useMemo(() => {
    let list = entities;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      list = list.filter(
        (e) => e.name.toLowerCase().includes(q) || (e.parent && e.parent.toLowerCase().includes(q))
      );
    }
    if (kindFilter) {
      list = list.filter((e) => e.kind === kindFilter);
    }
    return list;
  }, [entities, searchQuery, kindFilter]);

  const grouped = useMemo(() => {
    const acc = Object.create(null) as Record<string, CodeEntity[]>;
    for (const e of filtered) {
      const kind = e.kind || "unknown";
      if (!Object.hasOwn(acc, kind)) acc[kind] = [];
      acc[kind].push(e);
    }
    return acc;
  }, [filtered]);

  const sortedKinds = useMemo(
    () =>
      Object.keys(grouped).sort(
        (a, b) =>
          (KIND_ORDER.indexOf(a) === -1 ? 99 : KIND_ORDER.indexOf(a)) -
          (KIND_ORDER.indexOf(b) === -1 ? 99 : KIND_ORDER.indexOf(b))
      ),
    [grouped]
  );

  const toggleCollapse = (kind: string) =>
    setCollapsed((prev) => ({ ...prev, [kind]: !prev[kind] }));

  const toggleExpand = (kind: string) =>
    setExpanded((prev) => ({ ...prev, [kind]: !prev[kind] }));

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold mb-1">코드 분석</h2>
        <p className="text-sm text-muted-foreground">
          Java 소스코드를 파싱하여 패키지, 클래스, 메서드 구조를 추출합니다.
          코드 엔티티는 도메인 온톨로지와 매핑하는 기초 데이터가 됩니다.
        </p>
      </div>

      {/* Parse form */}
      <details className="rounded-lg border border-border bg-card">
        <summary className="px-4 py-2.5 text-xs font-medium cursor-pointer text-muted-foreground hover:text-foreground">
          새 Repository 파싱하기
        </summary>
        <div className="px-4 pb-4 pt-2 space-y-3 border-t border-border">
          <label className="text-xs font-medium text-foreground">Repository URL</label>
          <div className="flex gap-2">
            <input
              type="text"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              placeholder="https://github.com/org/repo.git"
              className="flex-1 px-3 py-1.5 text-sm bg-background border border-border rounded"
            />
            <button
              onClick={handleParse}
              disabled={parsing || !repoUrl.trim()}
              className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {parsing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Code className="h-3.5 w-3.5" />}
              Parse
            </button>
          </div>
        </div>
      </details>

      {/* Parse result */}
      {parseResult && (
        <div className="rounded-lg border border-green-300 dark:border-green-800 bg-green-50 dark:bg-green-950/20 p-3 text-sm">
          <p className="font-medium text-green-700 dark:text-green-400">파싱 완료</p>
          <p className="text-xs text-muted-foreground mt-1">
            파일 {parseResult.files_parsed}개 | 엔티티 {parseResult.entities_count}개 | 관계 {parseResult.relations_count}개
          </p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-950/20 p-3 text-sm text-red-700 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-12 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin mr-2" />
          Loading...
        </div>
      )}

      {/* Entity list with search + filter */}
      {!loading && entities.length > 0 && (
        <>
          {/* Search + Kind filter */}
          <div className="flex gap-3 items-center flex-wrap">
            <div className="relative flex-1 min-w-48">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="엔티티 검색..."
                className="w-full pl-8 pr-3 py-1.5 text-sm bg-background border border-border rounded"
              />
            </div>
            <div className="flex gap-1">
              <button
                onClick={() => setKindFilter(null)}
                className={`px-2.5 py-1 text-xs rounded-md border transition-colors ${
                  !kindFilter
                    ? "bg-primary text-primary-foreground border-primary"
                    : "border-border text-muted-foreground hover:text-foreground"
                }`}
              >
                전체 ({entities.length})
              </button>
              {KIND_ORDER.map((kind) => {
                const count = entities.filter((e) => e.kind === kind).length;
                if (count === 0) return null;
                return (
                  <button
                    key={kind}
                    onClick={() => setKindFilter(kindFilter === kind ? null : kind)}
                    className={`inline-flex items-center gap-1 px-2.5 py-1 text-xs rounded-md border transition-colors ${
                      kindFilter === kind
                        ? "bg-primary text-primary-foreground border-primary"
                        : "border-border text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {getIcon(kind)}
                    <span className="capitalize">{kind}</span>
                    <span>({count})</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Filtered results count */}
          {(searchQuery || kindFilter) && (
            <p className="text-xs text-muted-foreground">
              {filtered.length}개 결과
              {searchQuery && <> &middot; &ldquo;{searchQuery}&rdquo;</>}
              {kindFilter && <> &middot; {kindFilter}</>}
            </p>
          )}

          {/* Entity groups */}
          <div className="space-y-3">
            {sortedKinds.map((kind) => {
              const items = grouped[kind];
              const isCollapsed = !!collapsed[kind];
              const isExpanded = !!expanded[kind];
              const visibleItems = isExpanded ? items : items.slice(0, PAGE_SIZE);
              const hasMore = items.length > PAGE_SIZE && !isExpanded;

              return (
                <div key={kind} className="rounded-lg border border-border bg-card">
                  <button
                    onClick={() => toggleCollapse(kind)}
                    className="w-full flex items-center gap-2 px-4 py-2 border-b border-border bg-muted/30 hover:bg-muted/50 transition-colors"
                  >
                    {isCollapsed ? (
                      <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                    ) : (
                      <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                    )}
                    {getIcon(kind)}
                    <span className="text-sm font-medium capitalize">{kind}</span>
                    <span className="text-xs text-muted-foreground">({items.length})</span>
                  </button>
                  {!isCollapsed && (
                    <div className="divide-y divide-border">
                      {visibleItems.map((entity) => (
                        <div key={entity.id} className="px-4 py-1.5 flex items-center justify-between">
                          <div className="min-w-0">
                            <span className="text-sm font-mono">{entity.name}</span>
                            {entity.parent && (
                              <span className="text-xs text-muted-foreground ml-2 truncate">
                                &larr; {entity.parent}
                              </span>
                            )}
                          </div>
                          <span
                            className="text-[11px] text-muted-foreground truncate max-w-48 shrink-0 ml-2"
                            title={entity.file_path}
                          >
                            {entity.file_path}
                          </span>
                        </div>
                      ))}
                      {hasMore && (
                        <button
                          onClick={() => toggleExpand(kind)}
                          className="w-full px-4 py-2 text-xs text-primary hover:bg-muted/30 transition-colors"
                        >
                          + {items.length - PAGE_SIZE}개 더 보기
                        </button>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* Empty state */}
      {!loading && !error && entities.length === 0 && !parseResult && (
        <div className="text-center py-12 text-muted-foreground space-y-2">
          <Code className="h-8 w-8 mx-auto mb-2 opacity-30" />
          <p className="text-sm">이 Repository의 코드 엔티티가 없습니다.</p>
          <p className="text-xs">위에서 Repository URL을 입력하고 파싱하세요.</p>
        </div>
      )}
    </div>
  );
}
