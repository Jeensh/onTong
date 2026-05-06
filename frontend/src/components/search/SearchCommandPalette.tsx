"use client";

import { useEffect, useCallback, useMemo } from "react";
import { Loader2, Search, Sparkles, Filter, X } from "lucide-react";
import {
  CommandDialog,
  Command,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
} from "@/components/ui/command";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SearchResultItem } from "./SearchResultItem";
import { FilterSheet } from "./FilterSheet";
import {
  useSearchStore,
  type FilterSpec,
} from "@/lib/search/useSearchStore";
import { parseLightDSL } from "@/lib/search/dslParser";
import { useWorkspaceStore } from "@/lib/workspace/useWorkspaceStore";

interface ActiveChip {
  key: string;
  label: string;
  onRemove: () => void;
  tone?: "default" | "destructive";
}

function buildActiveChips(
  filters: FilterSpec,
  removeFilter: ReturnType<typeof useSearchStore.getState>["removeFilter"],
  mergeFilters: ReturnType<typeof useSearchStore.getState>["mergeFilters"]
): ActiveChip[] {
  const chips: ActiveChip[] = [];

  (filters.folders ?? []).forEach((v) => {
    chips.push({
      key: `folder:${v}`,
      label: `📁 ${v}`,
      onRemove: () => {
        const next = (filters.folders ?? []).filter((x) => x !== v);
        if (next.length) mergeFilters({ folders: next });
        else removeFilter("folders");
      },
    });
  });

  (filters.tags?.include ?? []).forEach((v) => {
    chips.push({
      key: `tag:${v}`,
      label: `🏷️ ${v}`,
      onRemove: () => {
        const include = (filters.tags?.include ?? []).filter((x) => x !== v);
        const nextTags = { ...(filters.tags ?? {}), include };
        if (!include.length && !(nextTags.exclude?.length)) removeFilter("tags");
        else mergeFilters({ tags: nextTags });
      },
    });
  });

  (filters.tags?.exclude ?? []).forEach((v) => {
    chips.push({
      key: `-tag:${v}`,
      label: `!🏷️ ${v}`,
      tone: "destructive",
      onRemove: () => {
        const exclude = (filters.tags?.exclude ?? []).filter((x) => x !== v);
        const nextTags = { ...(filters.tags ?? {}), exclude };
        if (!exclude.length && !(nextTags.include?.length)) removeFilter("tags");
        else mergeFilters({ tags: nextTags });
      },
    });
  });

  (filters.authors ?? []).forEach((v) => {
    chips.push({
      key: `author:${v}`,
      label: `👤 ${v}`,
      onRemove: () => {
        const next = (filters.authors ?? []).filter((x) => x !== v);
        if (next.length) mergeFilters({ authors: next });
        else removeFilter("authors");
      },
    });
  });

  (filters.types ?? []).forEach((v) => {
    chips.push({
      key: `type:${v}`,
      label: `📄 ${v}`,
      onRemove: () => {
        const next = (filters.types ?? []).filter((x) => x !== v);
        if (next.length) mergeFilters({ types: next });
        else removeFilter("types");
      },
    });
  });

  if (filters.mtime_from || filters.mtime_to) {
    const range = `${filters.mtime_from ?? ""}~${filters.mtime_to ?? ""}`;
    chips.push({
      key: `mtime:${range}`,
      label: `📅 ${range.replace(/~$/, " 이후").replace(/^~/, "~ ")}`,
      onRemove: () => {
        removeFilter("mtime_from");
        removeFilter("mtime_to");
      },
    });
  }

  (filters.statuses ?? []).forEach((v) => {
    chips.push({
      key: `status:${v}`,
      label: `🚦 ${v}`,
      onRemove: () => {
        const next = (filters.statuses ?? []).filter((x) => x !== v);
        if (next.length) mergeFilters({ statuses: next });
        else removeFilter("statuses");
      },
    });
  });

  (filters.acl ?? []).forEach((v) => {
    chips.push({
      key: `acl:${v}`,
      label: `🔐 ${v}`,
      onRemove: () => {
        const next = (filters.acl ?? []).filter((x) => x !== v);
        if (next.length) mergeFilters({ acl: next });
        else removeFilter("acl");
      },
    });
  });

  if (filters.boolean) {
    chips.push({
      key: "dsl",
      label: `⚡ DSL`,
      onRemove: () => removeFilter("boolean"),
    });
  }

  return chips;
}

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
    filters,
    filterSheetOpen,
    setFilterSheetOpen,
    setFilter,
    removeFilter,
    mergeFilters,
    clearFilters,
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

  // Light DSL: when user types `folder:X tag:Y rest`, promote to chips + keep residual
  const handleQueryChange = useCallback(
    (next: string) => {
      // Only try to promote on trailing space (token completed)
      if (next.endsWith(" ")) {
        const { query: residual, patch } = parseLightDSL(next);
        const hasPatch = Object.keys(patch).length > 0;
        if (hasPatch) {
          mergeFilters(patch);
          setQuery(residual + (residual ? " " : ""));
          return;
        }
      }
      setQuery(next);
    },
    [mergeFilters, setQuery]
  );

  const handleSelect = useCallback(
    (path: string) => {
      openTab(path);
      clear();
    },
    [openTab, clear]
  );

  const rawResults = searchMode === "local" ? results : semanticResults;
  const displayResults = rawResults.filter(
    (r, i, arr) => arr.findIndex((a) => a.path === r.path) === i
  );
  const isSearching = searchMode === "semantic" ? semanticLoading : false;

  const chips = useMemo(
    () => buildActiveChips(filters, removeFilter, mergeFilters),
    [filters, removeFilter, mergeFilters]
  );
  // silence unused-var warning for setFilter helper (kept for future integrations)
  void setFilter;

  return (
    <>
      <CommandDialog
        open={isOpen}
        onOpenChange={setOpen}
        title="문서 검색"
        description="문서를 검색하세요"
      >
        <Command shouldFilter={false}>
          <CommandInput
            placeholder="문서 검색... (folder:ERP author:@동해 ...)"
            value={query}
            onValueChange={handleQueryChange}
          />

          {/* Active filter chips + open-filter button */}
          <div className="flex flex-wrap items-center gap-1 px-3 py-2 border-b">
            {chips.map((c) => (
              <Badge
                key={c.key}
                variant={c.tone === "destructive" ? "destructive" : "secondary"}
                className="gap-1 pr-1"
              >
                <span className="truncate max-w-[180px]">{c.label}</span>
                <button
                  type="button"
                  aria-label={`${c.label} 제거`}
                  className="rounded-full hover:bg-black/10 p-0.5"
                  onClick={c.onRemove}
                >
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            ))}
            <Button
              variant="outline"
              size="sm"
              className="h-6 px-2 text-xs gap-1"
              onClick={() => setFilterSheetOpen(true)}
            >
              <Filter className="h-3 w-3" />+ 필터
            </Button>
            {chips.length > 0 && (
              <button
                type="button"
                className="text-[10px] text-muted-foreground hover:text-foreground ml-auto"
                onClick={clearFilters}
              >
                모두 지우기
              </button>
            )}
          </div>

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
              <CommandEmpty>
                <EmptyResultSuggestions
                  chips={chips}
                  filters={filters}
                  clearFilters={clearFilters}
                  mergeFilters={mergeFilters}
                  removeFilter={removeFilter}
                />
              </CommandEmpty>
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
                    status={
                      "status" in r ? (r as { status: string }).status : undefined
                    }
                    onClick={() => handleSelect(r.path)}
                  />
                ))}
              </CommandGroup>
            )}

            {!query.trim() && !isSearching && chips.length === 0 && (
              <div className="py-8 text-center text-sm text-muted-foreground">
                <Search className="h-8 w-8 mx-auto mb-2 opacity-30" />
                <p>문서 제목, 내용, 태그로 검색하세요</p>
                <p className="text-xs mt-1 opacity-60">
                  의미 검색으로 유사한 내용도 찾을 수 있습니다
                </p>
                <p className="text-[10px] mt-2 opacity-50">
                  팁:{" "}
                  <code className="font-mono bg-muted px-1 py-0.5 rounded">
                    folder:ERP author:@동해
                  </code>{" "}
                  처럼 입력 후 스페이스
                </p>
              </div>
            )}

            {!query.trim() && !isSearching && chips.length > 0 && (
              <div className="py-6 text-center text-xs text-muted-foreground">
                필터가 설정되어 있습니다. 검색어를 입력하거나 필터를 제거하세요.
              </div>
            )}
          </CommandList>
        </Command>
      </CommandDialog>

      {/* FilterSheet renders outside CommandDialog because it uses its own fixed layer */}
      {filterSheetOpen && <FilterSheet />}
    </>
  );
}

function EmptyResultSuggestions({
  chips,
  filters,
  clearFilters,
  mergeFilters,
  removeFilter,
}: {
  chips: ActiveChip[];
  filters: FilterSpec;
  clearFilters: () => void;
  mergeFilters: (patch: Partial<FilterSpec>) => void;
  removeFilter: (key: keyof FilterSpec) => void;
}) {
  if (chips.length === 0) {
    return (
      <div className="py-4 text-center text-sm text-muted-foreground">
        검색 결과가 없습니다.
        <p className="text-xs mt-1 opacity-70">다른 키워드로 시도해보세요.</p>
      </div>
    );
  }

  const hasMtime = Boolean(filters.mtime_from || filters.mtime_to);
  const relaxMtime90 = () => {
    const d = new Date();
    d.setDate(d.getDate() - 90);
    mergeFilters({ mtime_from: d.toISOString().slice(0, 10), mtime_to: undefined });
  };
  const dropMtime = () => {
    removeFilter("mtime_from");
    removeFilter("mtime_to");
  };

  return (
    <div className="px-3 py-4 text-left" role="group" aria-label="필터 완화 제안">
      <p className="text-sm text-foreground mb-1">검색 결과가 없습니다.</p>
      <p className="text-xs text-muted-foreground mb-3">
        조건을 완화해보세요. 필터를 하나씩 제거하거나 기간을 넓힐 수 있습니다.
      </p>

      <div className="flex flex-wrap gap-1.5 mb-3">
        {chips.map((c) => (
          <button
            key={c.key}
            type="button"
            onClick={c.onRemove}
            className="inline-flex items-center gap-1 rounded-md border border-dashed border-muted-foreground/40 px-2 py-0.5 text-xs text-muted-foreground hover:border-destructive/60 hover:text-destructive hover:bg-destructive/5"
            title={`"${c.label}" 필터만 제거`}
            aria-label={`${c.label} 필터만 제거하고 재검색`}
          >
            <X className="h-3 w-3" />
            {c.label}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap gap-1.5">
        {hasMtime && (
          <>
            <Button variant="outline" size="sm" className="text-xs h-7" onClick={relaxMtime90}>
              📅 기간을 최근 90일로 확장
            </Button>
            <Button variant="outline" size="sm" className="text-xs h-7" onClick={dropMtime}>
              📅 기간 필터 해제
            </Button>
          </>
        )}
        <Button variant="secondary" size="sm" className="text-xs h-7" onClick={clearFilters}>
          모든 필터 제거
        </Button>
      </div>
    </div>
  );
}
