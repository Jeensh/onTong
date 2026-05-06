"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ChevronRight, ChevronDown, Folder, FolderOpen, Box, Loader2, Search, X as XIcon,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  ontologyApi,
  type ModuleInventoryItemDTO,
  type ModuleNodeDTO,
  type ModulesResponseDTO,
  type SearchHitDTO,
} from "@/lib/api/ontology";
import { useWorkbench } from "./store";

/**
 * 좌측 navigator (V7 IA, D plan).
 * 5 mock tab (Map/Code/Domain/Action/큐) 대신 패키지 계층 트리.
 *
 * - 상단: 검색 (label/path 부분 매치)
 * - 트리: Maven module / package 계층, 각 노드 inventory 카운트
 * - leaf 클릭 또는 expand: 우측 inventory 패널에 그 패키지의 CodeType list
 *
 * 5000+ class 가정 → 트리 자체는 가벼움 (서버에서 집계). 잎 패키지의 inventory 만 lazy load.
 */
const SEARCH_PAGE_SIZE = 25;

export function ModuleTree() {
  const {
    activeRepoId,
    setSelectedCodeType,
    selectedCodeTypeFqn,
    setSelectedAction,
    setSelectedTerm,
  } = useWorkbench();
  const [data, setData] = useState<ModulesResponseDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [selectedPkg, setSelectedPkg] = useState<string | null>(null);
  const [inventory, setInventory] = useState<ModuleInventoryItemDTO[]>([]);
  const [invLoading, setInvLoading] = useState(false);
  const [searchQ, setSearchQ] = useState("");

  // Per-package inventory cache for inline tree rendering. Populated when a
  // package with direct classes is expanded. Lazy — we only fetch what the
  // user actually opens, so the 5K-class assumption stays cheap.
  const [invByPkg, setInvByPkg] = useState<Record<string, ModuleInventoryItemDTO[]>>({});
  const [invByPkgLoading, setInvByPkgLoading] = useState<Record<string, boolean>>({});

  // Backend full-text search across class / method / term / action / rule.
  // The previous local-only filter only matched package paths, so classes
  // were invisible. Now we hit /api/ontology/search and paginate.
  const [searchResults, setSearchResults] = useState<SearchHitDTO[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchLimit, setSearchLimit] = useState<number>(SEARCH_PAGE_SIZE);
  const [searchHasMore, setSearchHasMore] = useState<boolean>(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  // 트리 로드
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    ontologyApi.getModules(activeRepoId, 1)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setErr(e instanceof Error ? e.message : String(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [activeRepoId]);

  // 첫 로드 시 root chain 자동 expand (3 depth) — slabdesign 까지 보이게
  useEffect(() => {
    if (!data) return;
    const auto: string[] = [];
    let cur: ModuleNodeDTO | undefined = data.root;
    for (let i = 0; i < 4 && cur; i++) {
      auto.push(cur.path);
      cur = cur.children[0];
    }
    setExpanded(new Set(auto));
  }, [data]);

  // Reset pagination whenever the query changes.
  useEffect(() => {
    setSearchLimit(SEARCH_PAGE_SIZE);
  }, [searchQ]);

  // Debounced backend search. Hits /api/ontology/search which covers
  // code_type / code_method / term / action / rule.
  useEffect(() => {
    const q = searchQ.trim();
    if (!q) {
      setSearchResults([]);
      setSearchHasMore(false);
      setSearchError(null);
      setSearchLoading(false);
      return;
    }
    let cancelled = false;
    setSearchLoading(true);
    setSearchError(null);
    // The backend caps at 200 — we ask for limit+1 so we can detect "more".
    const askLimit = Math.min(searchLimit + 1, 200);
    const t = setTimeout(() => {
      ontologyApi
        .search(q, { repo_id: activeRepoId, limit: askLimit })
        .then((d) => {
          if (cancelled) return;
          const more = d.length > searchLimit;
          setSearchResults(more ? d.slice(0, searchLimit) : d);
          setSearchHasMore(more);
        })
        .catch((e) => {
          if (!cancelled) setSearchError(e instanceof Error ? e.message : String(e));
        })
        .finally(() => {
          if (!cancelled) setSearchLoading(false);
        });
    }, 200);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [searchQ, activeRepoId, searchLimit]);

  const onPickSearchHit = (hit: SearchHitDTO) => {
    if (hit.kind === "code_type") setSelectedCodeType(hit.fqn);
    else if (hit.kind === "action") setSelectedAction(hit.fqn);
    else if (hit.kind === "term") setSelectedTerm(hit.fqn);
    else if (hit.kind === "code_method") {
      // method 의 parent type fqn 으로 fallback selection (Authoring 입력으로 사용 가능)
      const parent = hit.fqn.replace(/[.#][^.#]+$/, "");
      if (parent) setSelectedCodeType(parent);
    }
    // rule — 별도 selection 없음 (앞으로 추가 가능)
  };

  // 패키지 선택 → inventory load
  useEffect(() => {
    if (!selectedPkg) { setInventory([]); return; }
    let cancelled = false;
    setInvLoading(true);
    ontologyApi
      .getModuleInventory(activeRepoId, { package: selectedPkg, recursive: false })
      .then((items) => { if (!cancelled) setInventory(items); })
      .catch(() => { if (!cancelled) setInventory([]); })
      .finally(() => { if (!cancelled) setInvLoading(false); });
    return () => { cancelled = true; };
  }, [selectedPkg, activeRepoId]);

  const toggle = (path: string) => {
    setExpanded((s) => {
      const next = new Set(s);
      next.has(path) ? next.delete(path) : next.add(path);
      return next;
    });
  };

  // Lazy fetch a package's inventory the first time it gets expanded.
  const ensureInventoryFor = (path: string) => {
    if (invByPkg[path] !== undefined) return; // cached
    if (invByPkgLoading[path]) return;
    setInvByPkgLoading((s) => ({ ...s, [path]: true }));
    ontologyApi
      .getModuleInventory(activeRepoId, { package: path, recursive: false })
      .then((items) => setInvByPkg((s) => ({ ...s, [path]: items })))
      .catch(() => setInvByPkg((s) => ({ ...s, [path]: [] })))
      .finally(() => setInvByPkgLoading((s) => ({ ...s, [path]: false })));
  };

  // 검색 매치 (path / name / 그 아래 모든 자식 path)
  const matchedPaths = useMemo(() => {
    if (!searchQ.trim() || !data) return null;
    const q = searchQ.trim().toLowerCase();
    const acc: Set<string> = new Set();
    const walk = (n: ModuleNodeDTO) => {
      const hit = n.name.toLowerCase().includes(q) || n.path.toLowerCase().includes(q);
      if (hit) {
        acc.add(n.path);
        // 부모 chain 도 expand 대상
        const parts = n.path.split(".");
        for (let i = 1; i < parts.length; i++) {
          acc.add(parts.slice(0, i).join("."));
        }
      }
      n.children.forEach(walk);
    };
    walk(data.root);
    return acc;
  }, [searchQ, data]);

  const visibleCheck = (n: ModuleNodeDTO): boolean => {
    if (matchedPaths === null) return true;
    return matchedPaths.has(n.path) || n.children.some(visibleCheck);
  };

  const renderNode = (n: ModuleNodeDTO, depth: number): React.ReactNode => {
    const isExpanded = expanded.has(n.path) || (matchedPaths?.has(n.path) ?? false);
    const isSelected = selectedPkg === n.path;
    const hasChildren = n.children.length > 0;
    const hasDirectClasses = n.direct_classes > 0;
    // A package can be expanded for two reasons: it has child packages
    // (folder behaviour), or it has direct classes (we want to show them
    // inline like leaves). The chevron is shown if either applies.
    const isToggleable = hasChildren || hasDirectClasses;

    const inlineClasses = invByPkg[n.path];
    const inlineLoading = invByPkgLoading[n.path];

    // When the user expands a package with direct classes, fetch its
    // inventory once so we can render classes inline as tree leaves.
    if (isExpanded && hasDirectClasses && inlineClasses === undefined && !inlineLoading) {
      ensureInventoryFor(n.path);
    }

    return (
      <div key={n.path}>
        <button
          onClick={() => {
            if (isToggleable) toggle(n.path);
            if (hasDirectClasses) setSelectedPkg(n.path);
          }}
          className={cn(
            "w-full text-left px-1 py-0.5 text-[12px] flex items-center gap-1 hover:bg-muted/50 transition-colors",
            isSelected && "bg-primary/10 text-foreground",
          )}
          style={{ paddingLeft: 4 + depth * 12 }}
        >
          {isToggleable ? (
            isExpanded ? <ChevronDown className="w-3 h-3 shrink-0" />
                       : <ChevronRight className="w-3 h-3 shrink-0" />
          ) : <span className="w-3 h-3 shrink-0" />}
          {hasChildren
            ? (isExpanded ? <FolderOpen className="w-3 h-3 shrink-0 text-amber-500" />
                          : <Folder className="w-3 h-3 shrink-0 text-amber-500" />)
            : <Box className="w-3 h-3 shrink-0 text-muted-foreground" />}
          <span className="truncate flex-1">{n.name}</span>
          {(n.direct_classes > 0 || n.total_classes > 0) && (
            <span className="text-[9.5px] text-muted-foreground/70 font-mono shrink-0">
              {n.direct_classes > 0 && <span>{n.direct_classes}</span>}
              {n.direct_classes > 0 && n.total_classes !== n.direct_classes && (
                <span>/{n.total_classes}</span>
              )}
              {n.direct_classes === 0 && n.total_classes > 0 && <span>·{n.total_classes}</span>}
              {n.direct_terms > 0 && <span className="text-violet-400 ml-1">T{n.direct_terms}</span>}
              {n.direct_actions > 0 && <span className="text-orange-400 ml-1">A{n.direct_actions}</span>}
            </span>
          )}
        </button>

        {isExpanded && (
          <div>
            {/* Sub-packages first */}
            {hasChildren && n.children.filter(visibleCheck).map((c) => renderNode(c, depth + 1))}

            {/* Then direct classes inline as tree leaves (for expanded packages
                that have direct_classes>0) — so the user never has to look at
                a separate inventory panel. */}
            {hasDirectClasses && inlineLoading && (
              <div
                className="text-[10px] text-muted-foreground py-0.5 flex items-center gap-1"
                style={{ paddingLeft: 4 + (depth + 1) * 12 + 16 }}
              >
                <Loader2 className="w-3 h-3 animate-spin" />
                <span>클래스 로딩…</span>
              </div>
            )}
            {hasDirectClasses && inlineClasses && inlineClasses.map((it) => {
              const isClassSelected = selectedCodeTypeFqn === it.fqn;
              return (
                <button
                  key={it.fqn}
                  onClick={() => setSelectedCodeType(it.fqn)}
                  className={cn(
                    "w-full text-left px-1 py-0.5 text-[11.5px] flex items-center gap-1 hover:bg-muted/50 transition-colors",
                    isClassSelected && "bg-primary/20 text-foreground ring-1 ring-primary/40",
                  )}
                  style={{ paddingLeft: 4 + (depth + 1) * 12 + 16 }}
                  title={it.fqn}
                >
                  <RoleDot role={it.role} />
                  <span className={cn("truncate flex-1 font-mono", isClassSelected && "font-semibold")}>
                    {it.simple_name}
                  </span>
                  {it.has_term && (
                    <span className="text-[9px] text-violet-400 shrink-0" title="primary term mapping">★</span>
                  )}
                  <span className="text-[9px] text-muted-foreground/60 font-mono shrink-0">{it.method_count}m</span>
                </button>
              );
            })}
          </div>
        )}
      </div>
    );
  };

  const isSearching = searchQ.trim().length > 0;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-2 py-1.5 border-b border-border">
        <div className="relative">
          <Search className="absolute left-1.5 top-1/2 -translate-y-1/2 w-3 h-3 text-muted-foreground pointer-events-none" />
          <Input
            value={searchQ}
            onChange={(e) => setSearchQ(e.target.value)}
            placeholder="검색 (클래스 / 메서드 / Term / Action)"
            className="pl-6 pr-7 h-7 text-[11px]"
          />
          {isSearching && (
            <button
              type="button"
              onClick={() => setSearchQ("")}
              title="검색어 지우기"
              className="absolute right-1 top-1/2 -translate-y-1/2 p-0.5 rounded hover:bg-muted text-muted-foreground hover:text-foreground"
            >
              <XIcon className="w-3 h-3" />
            </button>
          )}
        </div>
        {data && !isSearching && (
          <div className="text-[10px] text-muted-foreground mt-1 font-mono">
            {data.flat_count} CodeType
          </div>
        )}
        {isSearching && (
          <div className="text-[10px] text-muted-foreground mt-1 font-mono">
            {searchLoading
              ? "검색 중…"
              : searchError
              ? `오류: ${searchError}`
              : `${searchResults.length}건${searchHasMore ? "+" : ""} 매칭`}
          </div>
        )}
      </div>

      {/* Search results panel — replaces tree while query is active */}
      {isSearching ? (
        <div className="overflow-y-auto flex-1 py-1">
          {searchLoading && searchResults.length === 0 && (
            <div className="flex items-center justify-center p-4">
              <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
            </div>
          )}
          {!searchLoading && searchResults.length === 0 && !searchError && (
            <div className="text-[11px] text-muted-foreground p-3 italic">
              매칭 없음. 다른 키워드 시도해보세요 (대소문자 무관, 부분 매치 OK)
            </div>
          )}
          {searchResults.map((hit) => {
            const isCodeTypeSelected =
              hit.kind === "code_type" && selectedCodeTypeFqn === hit.fqn;
            const simple = hit.fqn.split(/[.#]/).pop() ?? hit.fqn;
            const parent = hit.fqn.slice(0, hit.fqn.length - simple.length).replace(/[.#]$/, "");
            return (
              <button
                key={`${hit.kind}|${hit.fqn}`}
                onClick={() => onPickSearchHit(hit)}
                title={hit.fqn}
                className={cn(
                  "w-full text-left px-2 py-1 text-[11px] hover:bg-muted/50 border-b border-border/40 last:border-b-0 flex items-center gap-1.5",
                  isCodeTypeSelected && "bg-primary/15 ring-1 ring-primary/40",
                )}
              >
                <KindBadge kind={hit.kind} />
                <span className={cn("font-mono truncate flex-1", isCodeTypeSelected && "font-semibold")}>
                  {simple}
                </span>
                {hit.label && hit.label !== simple && (
                  <span className="text-[10px] text-muted-foreground truncate" title={hit.label}>
                    {hit.label}
                  </span>
                )}
                {parent && (
                  <span className="text-[9px] text-muted-foreground/70 truncate max-w-[40%]" title={parent}>
                    {parent}
                  </span>
                )}
              </button>
            );
          })}
          {searchHasMore && !searchLoading && (
            <div className="p-2">
              <button
                type="button"
                onClick={() =>
                  setSearchLimit((n) => Math.min(n + SEARCH_PAGE_SIZE, 200))
                }
                className="w-full text-[11px] py-1.5 rounded border border-border bg-muted/40 hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
              >
                더보기 (+{SEARCH_PAGE_SIZE})
              </button>
              {searchLimit >= 200 && (
                <div className="text-[10px] text-muted-foreground italic text-center mt-1">
                  최대 200건. 더 좁은 키워드 사용 권장.
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        // Tree (검색어 비어있을 때)
        <div className="overflow-y-auto flex-1 py-1">
          {loading && (
            <div className="flex items-center justify-center p-4">
              <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
            </div>
          )}
          {err && (
            <div className="text-[11px] text-destructive p-3">
              트리 로드 실패: {err}
              <div className="text-muted-foreground mt-1">
                먼저 Import 가 필요합니다.
              </div>
            </div>
          )}
          {data && data.root.children.filter(visibleCheck).map((c) => renderNode(c, 0))}
        </div>
      )}

      {/* Inventory panel — 선택된 패키지 안의 CodeType list */}
      {selectedPkg && (
        <div className="border-t border-border max-h-72 overflow-hidden flex flex-col">
          <div className="px-2 py-1 bg-muted/40 text-[10px] font-mono text-muted-foreground truncate flex items-center justify-between">
            <span className="truncate" title={selectedPkg}>{selectedPkg}</span>
            <button
              onClick={() => setSelectedPkg(null)}
              className="text-muted-foreground hover:text-foreground"
            >
              ✕
            </button>
          </div>
          <div className="overflow-y-auto flex-1">
            {invLoading ? (
              <div className="p-3"><Loader2 className="w-3 h-3 animate-spin" /></div>
            ) : inventory.length === 0 ? (
              <p className="text-[10px] text-muted-foreground p-2">직접 클래스 없음</p>
            ) : (
              inventory.map((it) => (
                <button
                  key={it.fqn}
                  onClick={() => setSelectedCodeType(it.fqn)}
                  className="w-full text-left px-2 py-1 text-[11px] hover:bg-muted border-b border-border last:border-b-0 flex items-center gap-1"
                >
                  <RoleDot role={it.role} />
                  <span className="truncate flex-1">{it.simple_name}</span>
                  {it.has_term && (
                    <span className="text-[9px] text-violet-400 shrink-0" title="primary term mapping">
                      ★
                    </span>
                  )}
                  <span className="text-[9px] text-muted-foreground/60 font-mono shrink-0">
                    {it.method_count}m
                  </span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function KindBadge({ kind }: { kind: SearchHitDTO["kind"] }) {
  // Tiny color-coded badge so the user can scan a result list and tell
  // class / method / term / action / rule apart at a glance.
  const map: Record<SearchHitDTO["kind"], { label: string; cls: string }> = {
    code_type:   { label: "class", cls: "bg-primary/10 text-primary border-primary/40" },
    code_method: { label: "mtd",   cls: "bg-amber-400/10 text-amber-300 border-amber-400/40" },
    term:        { label: "term",  cls: "bg-violet-400/10 text-violet-300 border-violet-400/40" },
    action:      { label: "act",   cls: "bg-orange-400/10 text-orange-300 border-orange-400/40" },
    rule:        { label: "rule",  cls: "bg-pink-400/10 text-pink-300 border-pink-400/40" },
  };
  const m = map[kind];
  return (
    <span
      className={cn(
        "text-[9px] uppercase font-semibold border rounded px-1 py-0 shrink-0 w-9 text-center",
        m.cls,
      )}
    >
      {m.label}
    </span>
  );
}

function RoleDot({ role }: { role: string }) {
  const color =
    role === "domain" ? "#a78bfa" :
    role === "framework" ? "#94a3b8" :
    role === "infra" ? "#fbbf24" :
    "#cbd5e1";
  return (
    <span
      className="inline-block rounded-full shrink-0"
      style={{ width: 6, height: 6, background: color }}
      title={role}
    />
  );
}
