"use client";

import { useEffect, useCallback } from "react";
import { Loader2, Search, Sparkles } from "lucide-react";
import {
  CommandDialog,
  Command,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
} from "@/components/ui/command";
import { SearchResultItem } from "./SearchResultItem";
import { useSearchStore } from "@/lib/search/useSearchStore";
import { useWorkspaceStore } from "@/lib/workspace/useWorkspaceStore";

export function SearchCommandPalette() {
  const {
    isOpen,
    setOpen,
    query,
    setQuery,
    results,
    searchMode,
    setSearchMode,
    semanticResults,
    semanticLoading,
    isLoading,
    searchSemantic,
    clear,
  } = useSearchStore();

  const openTab = useWorkspaceStore((s) => s.openTab);

  // Debounced semantic search
  useEffect(() => {
    if (searchMode !== "semantic" || !query.trim()) return;
    const timer = setTimeout(() => {
      searchSemantic(query);
    }, 300);
    return () => clearTimeout(timer);
  }, [query, searchMode, searchSemantic]);

  const handleSelect = useCallback(
    (path: string) => {
      openTab(path);
      clear();
    },
    [openTab, clear]
  );

  const rawResults =
    searchMode === "local" ? results : semanticResults;
  // Deduplicate by path (hybrid search may return multiple chunks from same file)
  const displayResults = rawResults.filter(
    (r, i, arr) => arr.findIndex((a) => a.path === r.path) === i
  );
  const isSearching =
    searchMode === "semantic" ? semanticLoading : false;

  return (
    <CommandDialog
      open={isOpen}
      onOpenChange={setOpen}
      title="문서 검색"
      description="문서를 검색하세요"
    >
      <Command shouldFilter={false}>
        <CommandInput
          placeholder="문서 검색... (Ctrl+K)"
          value={query}
          onValueChange={setQuery}
        />

        {/* Mode toggle */}
        <div className="flex items-center gap-1 px-3 py-1.5 border-b">
          <button
            className={`flex items-center gap-1 px-2 py-0.5 rounded text-xs transition-colors ${
              searchMode === "local"
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted"
            }`}
            onClick={() => setSearchMode("local")}
          >
            <Search className="h-3 w-3" />
            키워드
          </button>
          <button
            className={`flex items-center gap-1 px-2 py-0.5 rounded text-xs transition-colors ${
              searchMode === "semantic"
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted"
            }`}
            onClick={() => setSearchMode("semantic")}
          >
            <Sparkles className="h-3 w-3" />
            의미 검색
          </button>
          {isLoading && (
            <span className="text-[10px] text-muted-foreground ml-auto flex items-center gap-1">
              <Loader2 className="h-3 w-3 animate-spin" />
              인덱스 로딩...
            </span>
          )}
        </div>

        <CommandList className="max-h-80">
          {isSearching && (
            <div className="flex items-center justify-center py-6 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
              검색 중...
            </div>
          )}

          {!isSearching && query.trim() && displayResults.length === 0 && (
            <CommandEmpty>검색 결과가 없습니다</CommandEmpty>
          )}

          {!isSearching && displayResults.length > 0 && (
            <CommandGroup heading={`${displayResults.length}개 결과`}>
              {displayResults.map((r) => (
                <SearchResultItem
                  key={r.path}
                  title={r.title}
                  path={r.path}
                  snippet={r.snippet}
                  tags={r.tags}
                  query={query}
                  status={"status" in r ? (r as { status: string }).status : undefined}
                  onClick={() => handleSelect(r.path)}
                />
              ))}
            </CommandGroup>
          )}

          {!query.trim() && !isSearching && (
            <div className="py-8 text-center text-sm text-muted-foreground">
              <Search className="h-8 w-8 mx-auto mb-2 opacity-30" />
              <p>문서 제목, 내용, 태그로 검색하세요</p>
              <p className="text-xs mt-1 opacity-60">
                의미 검색으로 유사한 내용도 찾을 수 있습니다
              </p>
            </div>
          )}
        </CommandList>
      </Command>
    </CommandDialog>
  );
}
