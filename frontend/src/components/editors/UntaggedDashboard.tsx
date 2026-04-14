"use client";

import { useCallback, useEffect, useState } from "react";
import { useWorkspaceStore } from "@/lib/workspace/useWorkspaceStore";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Check, ChevronLeft, ChevronRight, Loader2, RefreshCw, Sparkles } from "lucide-react";
import { toast } from "sonner";
import type { MetadataSuggestion } from "@/types";

interface UntaggedFile {
  path: string;
  title: string;
}

interface BulkResultItem {
  path: string;
  suggestion?: MetadataSuggestion;
  applied: boolean;
  error?: string;
}

const PAGE_SIZE = 20;

export function UntaggedDashboard() {
  const [files, setFiles] = useState<UntaggedFile[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [bulkLoading, setBulkLoading] = useState(false);
  const [results, setResults] = useState<Record<string, BulkResultItem>>({});
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [stats, setStats] = useState<{ domains: Record<string, number>; tags: Record<string, number>; untagged_count: number } | null>(null);
  const openTab = useWorkspaceStore((s) => s.openTab);

  const fetchPage = useCallback((pageOffset: number) => {
    setLoading(true);
    setResults({});
    fetch(`/api/metadata/untagged?offset=${pageOffset}&limit=${PAGE_SIZE}`)
      .then((r) => r.json())
      .then((d) => {
        setFiles(d.files || []);
        setTotalCount(d.count || 0);
        setOffset(pageOffset);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => { fetchPage(0); }, [fetchPage]);

  useEffect(() => {
    fetch("/api/metadata/stats")
      .then((r) => r.json())
      .then(setStats)
      .catch(() => {});
  }, []);

  const totalPages = Math.ceil(totalCount / PAGE_SIZE);
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  const handleBulkSuggest = useCallback(
    async (apply: boolean) => {
      if (files.length === 0) return;
      if (apply && !confirm(`현재 페이지 ${files.length}개 문서에 자동 태깅을 적용합니다. 계속할까요?`)) return;

      setBulkLoading(true);
      setProgress({ done: 0, total: files.length });

      try {
        const res = await fetch("/api/metadata/suggest-bulk", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ paths: files.map((f) => f.path), apply }),
        });
        if (!res.ok) throw new Error("Bulk suggest failed");
        const data = await res.json();
        const newResults: Record<string, BulkResultItem> = {};
        for (const r of data.results) {
          newResults[r.path] = r;
        }
        setResults(newResults);
        setProgress({ done: files.length, total: files.length });

        if (apply) {
          const applied = Object.values(newResults).filter((r) => r.applied).length;
          toast.success(`${applied}/${files.length}개 문서 자동 태깅 완료`);
          fetchPage(offset);
        }
      } catch {
        const errResults: Record<string, BulkResultItem> = {};
        for (const f of files) {
          errResults[f.path] = { path: f.path, applied: false, error: "요청 실패" };
        }
        setResults(errResults);
      }

      setBulkLoading(false);
    },
    [files, fetchPage, offset]
  );

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6">
      <div>
        <h2 className="text-lg font-bold">미태깅 문서 대시보드</h2>
        <p className="text-sm text-muted-foreground mt-1">
          메타데이터(Domain, Process, Tags)가 없는 문서 목록입니다.
        </p>
      </div>

      {stats && (
        <div className="grid grid-cols-3 gap-3">
          <div className="border rounded-lg p-3 text-center">
            <div className="text-2xl font-bold">{Object.keys(stats.domains).length}</div>
            <div className="text-xs text-muted-foreground">Domains</div>
          </div>
          <div className="border rounded-lg p-3 text-center">
            <div className="text-2xl font-bold">{Object.keys(stats.tags).length}</div>
            <div className="text-xs text-muted-foreground">Tags</div>
          </div>
          <div className="border rounded-lg p-3 text-center">
            <div className="text-2xl font-bold">{stats.untagged_count}</div>
            <div className="text-xs text-muted-foreground">미태깅</div>
          </div>
        </div>
      )}

      <div className="border rounded-lg">
        <div className="flex items-center justify-between px-4 py-3 border-b">
          <span className="text-sm font-medium">
            미태깅 문서 ({loading ? "..." : totalCount}건)
          </span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" className="h-7 gap-1 text-xs" onClick={() => fetchPage(offset)}>
              <RefreshCw className="h-3 w-3" />
            </Button>
            {files.length > 0 && (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 gap-1 text-xs"
                  onClick={() => handleBulkSuggest(false)}
                  disabled={bulkLoading}
                >
                  {bulkLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3" />}
                  미리보기
                </Button>
                <Button
                  size="sm"
                  className="h-7 gap-1 text-xs"
                  onClick={() => handleBulkSuggest(true)}
                  disabled={bulkLoading}
                >
                  {bulkLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3" />}
                  자동 태깅
                </Button>
              </>
            )}
          </div>
        </div>

        {bulkLoading && (
          <div className="px-4 py-2 text-xs text-muted-foreground">
            진행 중: {progress.done}/{progress.total}
            <div className="w-full bg-muted rounded-full h-1.5 mt-1">
              <div
                className="bg-primary rounded-full h-1.5 transition-all"
                style={{ width: `${progress.total > 0 ? (progress.done / progress.total) * 100 : 0}%` }}
              />
            </div>
          </div>
        )}

        {loading ? (
          <div className="p-4 text-sm text-muted-foreground text-center">
            <Loader2 className="h-4 w-4 animate-spin inline mr-2" />
            로딩 중...
          </div>
        ) : files.length === 0 && totalCount === 0 ? (
          <div className="p-8 text-center text-muted-foreground">
            <Check className="h-8 w-8 text-green-500 mx-auto mb-2" />
            <span className="text-sm">모든 문서에 메타데이터가 설정되어 있습니다</span>
          </div>
        ) : (
          <>
            <div className="divide-y">
              {files.map((f) => {
                const result = results[f.path];
                const suggestion = result?.suggestion;
                return (
                  <div key={f.path} className="px-4 py-2">
                    <div className="flex items-center justify-between">
                      <button
                        onClick={() => openTab(f.path)}
                        className="text-left text-sm text-blue-600 hover:underline dark:text-blue-400 truncate max-w-[70%]"
                      >
                        {f.path}
                      </button>
                      <div className="flex items-center gap-1">
                        {result?.applied && (
                          <Badge className="text-[10px] bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400">
                            적용됨
                          </Badge>
                        )}
                        {result?.error && (
                          <Badge variant="destructive" className="text-[10px]">{result.error}</Badge>
                        )}
                      </div>
                    </div>
                    {suggestion && !result?.applied && (
                      <div className="mt-1 flex items-center gap-1 flex-wrap">
                        {suggestion.confidence > 0 && (
                          <span className={`text-[10px] font-medium px-1 rounded ${
                            suggestion.confidence >= 0.7
                              ? "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400"
                              : suggestion.confidence >= 0.5
                              ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-400"
                              : "bg-red-100 text-red-600 dark:bg-red-900/40 dark:text-red-400"
                          }`}>
                            {Math.round(suggestion.confidence * 100)}%
                          </span>
                        )}
                        {suggestion.domain && <Badge variant="outline" className="text-[10px]">{suggestion.domain}</Badge>}
                        {suggestion.process && <Badge variant="outline" className="text-[10px]">{suggestion.process}</Badge>}
                        {suggestion.tags.map((t) => (
                          <Badge key={t} variant="secondary" className="text-[10px]">{t}</Badge>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 px-4 py-3 border-t">
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 w-7 p-0"
                  disabled={currentPage <= 1}
                  onClick={() => fetchPage(offset - PAGE_SIZE)}
                >
                  <ChevronLeft className="h-3 w-3" />
                </Button>
                <span className="text-xs text-muted-foreground">
                  {currentPage} / {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 w-7 p-0"
                  disabled={currentPage >= totalPages}
                  onClick={() => fetchPage(offset + PAGE_SIZE)}
                >
                  <ChevronRight className="h-3 w-3" />
                </Button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
