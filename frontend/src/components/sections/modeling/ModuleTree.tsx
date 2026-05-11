"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ChevronRight, ChevronDown, Folder, FolderOpen, Box, Loader2, Search, X as XIcon, Eye,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  ontologyApi,
  type ModuleActionInventoryItemDTO,
  type ModuleInventoryItemDTO,
  type ModuleNodeDTO,
  type ModulesResponseDTO,
  type SearchHitDTO,
} from "@/lib/api/ontology";
import { useWorkbench } from "./store";
import { HelpHint } from "./HelpHint";

/**
 * 좌측 navigator (V7 IA, D plan).
 * 5 mock tab (Map/Code/Domain/Action/큐) 대신 패키지 계층 트리.
 *
 * - 상단: 검색 (label/path 부분 매치)
 * - 트리: Maven module / package 계층, 각 노드 inventory 카운트
 * - 패키지 expand → 직접 클래스/Action 들이 트리 leaf 로 inline 노출 (lazy fetch).
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
    setSelectedRule,
    openPeek,
  } = useWorkbench();
  const [data, setData] = useState<ModulesResponseDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  // Highlighted package in the tree. Was previously also driving a bottom
  // inventory panel that duplicated the expanded children — removed in
  // Wave C cleanup. Kept for the row highlight + scroll affordance only.
  const [selectedPkg, setSelectedPkg] = useState<string | null>(null);
  const [searchQ, setSearchQ] = useState("");

  // Per-package inventory cache for inline tree rendering. Populated when a
  // package with direct classes is expanded. Lazy — we only fetch what the
  // user actually opens, so the 5K-class assumption stays cheap.
  const [invByPkg, setInvByPkg] = useState<Record<string, ModuleInventoryItemDTO[]>>({});
  const [invByPkgLoading, setInvByPkgLoading] = useState<Record<string, boolean>>({});
  // Action 버전 — direct_actions>0 인 패키지 expand 시 그 패키지 의 Action 들을 leaf 로 표시
  const [actByPkg, setActByPkg] = useState<Record<string, ModuleActionInventoryItemDTO[]>>({});
  const [actByPkgLoading, setActByPkgLoading] = useState<Record<string, boolean>>({});

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
      // Mirror FqnLink behaviour for code_method — primary click opens the
      // global Code Peek modal so the user can read the body without losing
      // the current Detail selection. (Old behaviour navigated to the parent
      // class, which was confusing — now matches Detail-pane FqnLinks.)
      openPeek({ kind: "code_method", fqn: hit.fqn, repoId: activeRepoId });
    }
    else if (hit.kind === "rule") setSelectedRule(hit.fqn);
  };

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

  // Action 인벤토리도 같은 방식으로 lazy load.
  const ensureActionsFor = (path: string) => {
    if (actByPkg[path] !== undefined) return;
    if (actByPkgLoading[path]) return;
    setActByPkgLoading((s) => ({ ...s, [path]: true }));
    ontologyApi
      .getModuleInventoryActions(activeRepoId, { package: path, recursive: false })
      .then((items) => setActByPkg((s) => ({ ...s, [path]: items })))
      .catch(() => setActByPkg((s) => ({ ...s, [path]: [] })))
      .finally(() => setActByPkgLoading((s) => ({ ...s, [path]: false })));
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

  /**
   * Single-child chain 압축 — n 이 직접 class/action/term 가 없고 자식이 1개면,
   * 자식과 합쳐 점선 prefix 로 표시. 사용자가 `com.example.slabdesign.feature.sd.process` 같은
   * 빈 chain 을 한 줄로 보게 함.
   *
   * matchedPaths 가 있을 때 (검색 중) 는 압축 건너뜀 — 검색 결과가 정확히 보이도록.
   */
  const compressChain = (start: ModuleNodeDTO): { display: ModuleNodeDTO; prefix: string[] } => {
    if (matchedPaths !== null) return { display: start, prefix: [] };
    let cur = start;
    const prefix: string[] = [];
    while (
      cur.children.length === 1 &&
      cur.direct_classes === 0 &&
      cur.direct_actions === 0 &&
      cur.direct_terms === 0
    ) {
      prefix.push(cur.name);
      cur = cur.children[0];
    }
    return { display: cur, prefix };
  };

  const renderNode = (input: ModuleNodeDTO, depth: number): React.ReactNode => {
    const { display: n, prefix } = compressChain(input);
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
    const hasDirectActions = n.direct_actions > 0;
    const inlineActions = actByPkg[n.path];
    const inlineActionLoading = actByPkgLoading[n.path];

    // When the user expands a package with direct classes, fetch its
    // inventory once so we can render classes inline as tree leaves.
    if (isExpanded && hasDirectClasses && inlineClasses === undefined && !inlineLoading) {
      ensureInventoryFor(n.path);
    }
    if (isExpanded && hasDirectActions && inlineActions === undefined && !inlineActionLoading) {
      ensureActionsFor(n.path);
    }

    // Package rows (containers — has children OR direct classes/actions) get a
    // subtle background tint so they visually separate from leaf class rows
    // when scrolling through hundreds of rows at 5K-class scale. Compressed
    // chains are still containers so they share the tint.
    const isPackageRow = hasChildren || hasDirectClasses || hasDirectActions;

    // Hover-only T/A counts to reduce visual noise at scale. The count info
    // is preserved in the row's title attribute as a keyboard-only fallback.
    const countTitle = [
      n.direct_terms > 0 ? `Term ${n.direct_terms}` : null,
      n.direct_actions > 0 ? `Action ${n.direct_actions}` : null,
    ].filter(Boolean).join(" · ");

    return (
      <div key={n.path}>
        <button
          onClick={() => {
            if (isToggleable) toggle(n.path);
            if (hasDirectClasses) setSelectedPkg(n.path);
          }}
          className={cn(
            "group w-full text-left px-1 py-0.5 text-[12px] flex items-center gap-1 hover:bg-muted/50 transition-colors",
            isPackageRow && !isSelected && "bg-muted/30",
            isSelected && "bg-primary/10 text-foreground",
          )}
          style={{ paddingLeft: 4 + depth * 12 }}
          title={countTitle || undefined}
        >
          {isToggleable ? (
            isExpanded ? <ChevronDown className="w-3 h-3 shrink-0" />
                       : <ChevronRight className="w-3 h-3 shrink-0" />
          ) : <span className="w-3 h-3 shrink-0" />}
          {hasChildren
            ? (isExpanded ? <FolderOpen className="w-3 h-3 shrink-0 text-amber-500" />
                          : <Folder className="w-3 h-3 shrink-0 text-amber-500" />)
            : <Box className="w-3 h-3 shrink-0 text-muted-foreground" />}
          <span className="truncate flex-1 min-w-0">
            {prefix.length > 0 && (
              <span className="text-muted-foreground/60 text-[11px]">{prefix.join(".")}.</span>
            )}
            <span>{n.name}</span>
          </span>
          {(n.direct_classes > 0 || n.total_classes > 0) && (
            <span className="text-[9.5px] text-muted-foreground/70 font-mono shrink-0">
              {n.direct_classes > 0 && <span>{n.direct_classes}</span>}
              {n.direct_classes > 0 && n.total_classes !== n.direct_classes && (
                <span>/{n.total_classes}</span>
              )}
              {n.direct_classes === 0 && n.total_classes > 0 && <span>·{n.total_classes}</span>}
              {(n.direct_terms > 0 || n.direct_actions > 0) && (
                <span className="opacity-0 group-hover:opacity-100 transition-opacity">
                  {n.direct_terms > 0 && <span className="text-violet-400 ml-1">T{n.direct_terms}</span>}
                  {n.direct_actions > 0 && <span className="text-orange-400 ml-1">A{n.direct_actions}</span>}
                </span>
              )}
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
            {/* Action leaves — 그 패키지에 매핑된 Action 들. 한 화면에서 매핑 검수
                가능하도록 class leaf 아래 같은 들여쓰기로 노출. */}
            {hasDirectActions && inlineActionLoading && (
              <div
                className="text-[10px] text-muted-foreground py-0.5 flex items-center gap-1"
                style={{ paddingLeft: 4 + (depth + 1) * 12 + 16 }}
              >
                <Loader2 className="w-3 h-3 animate-spin" />
                <span>Action 로딩…</span>
              </div>
            )}
            {hasDirectActions && inlineActions && inlineActions.map((a) => (
              <button
                key={a.fqn}
                onClick={() => setSelectedAction(a.fqn)}
                className="w-full text-left px-1 py-0.5 text-[11.5px] flex items-center gap-1 hover:bg-muted/50 transition-colors"
                style={{ paddingLeft: 4 + (depth + 1) * 12 + 16 }}
                title={`${a.fqn}\nkind: ${a.kind}\nlevel: ${a.verification_level}${a.primary_method_fqn ? `\n→ ${a.primary_method_fqn}` : ""}`}
              >
                <span className="w-2 h-2 shrink-0 rounded-sm bg-orange-500" aria-label="action" />
                <span className="truncate flex-1 font-mono text-foreground">
                  {a.name}
                </span>
                {a.confirmed ? (
                  <span className="shrink-0 inline-flex items-center gap-0.5">
                    <span className="text-[9px] text-emerald-700" title="confirmed (signature_locked 이상)">✓</span>
                    <HelpHint term="confirmed" inline />
                  </span>
                ) : (
                  <span className="shrink-0 inline-flex items-center gap-0.5">
                    <span className="text-[9px] text-amber-700" title="draft (큐에서 confirm 대기)">·</span>
                    <HelpHint term="draft" inline />
                  </span>
                )}
                <span className="text-[9px] text-muted-foreground/60 font-mono shrink-0">
                  {a.realization_count}r
                </span>
              </button>
            ))}
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
          {/* One-time kind legend so first-time users can decode the 5 KindBadges. */}
          {searchResults.length > 0 && <KindBadgeLegend />}
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
            // Peek eye icon for code_type (mirrors FqnLink). code_method's
            // primary click is already peek, so no extra eye needed there.
            const showPeekEye = hit.kind === "code_type";
            // Outer becomes a role=button div so we can nest a real <button>
            // (Eye / peek) without violating hydration.
            return (
              <div
                key={`${hit.kind}|${hit.fqn}`}
                role="button"
                tabIndex={0}
                onClick={() => onPickSearchHit(hit)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onPickSearchHit(hit);
                  }
                }}
                title={hit.fqn}
                className={cn(
                  "w-full text-left px-2 py-1 text-[11px] hover:bg-muted/50 border-b border-border/40 last:border-b-0 flex items-center gap-1.5 cursor-pointer",
                  isCodeTypeSelected && "bg-primary/15 ring-1 ring-primary/40",
                )}
              >
                <KindBadge kind={hit.kind} />
                <span className={cn("font-mono truncate flex-1 min-w-0", isCodeTypeSelected && "font-semibold")}>
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
                {showPeekEye && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      openPeek({ kind: "code_type", fqn: hit.fqn, repoId: activeRepoId });
                    }}
                    className="shrink-0 inline-flex items-center justify-center w-4 h-4 rounded text-muted-foreground hover:text-primary hover:bg-primary/10 transition-colors"
                    title="코드 미리보기 (현재 선택 유지)"
                    aria-label="코드 미리보기"
                  >
                    <Eye className="w-3 h-3" />
                  </button>
                )}
              </div>
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

export function RoleDot({ role }: { role: string }) {
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

/**
 * Sticky 1-line legend explaining RoleDot colors + tree's C/T/A counts.
 * Sits above the code tree so first-time users can read what the dots and
 * abbreviated counts mean without hovering each row. Kept tight (~36px max).
 */
export function RoleDotLegend() {
  const items: { role: string; label: string }[] = [
    { role: "domain", label: "domain" },
    { role: "framework", label: "framework" },
    { role: "infra", label: "infra" },
    { role: "unknown", label: "unknown" },
  ];
  return (
    <div className="px-2 py-0.5 border-b border-border bg-muted/20 text-[10px] text-muted-foreground">
      <div className="flex items-center gap-2 flex-wrap">
        {items.map((it, i) => (
          <span key={it.role} className="inline-flex items-center gap-1">
            <RoleDot role={it.role} />
            <span>{it.label}</span>
            {i === 0 && <HelpHint term="role" inline />}
            {i < items.length - 1 && <span className="text-muted-foreground/40 ml-1">·</span>}
          </span>
        ))}
      </div>
      <div className="flex items-center gap-1.5 flex-wrap mt-0.5">
        <span className="text-muted-foreground/70">카운트:</span>
        <span className="inline-flex items-center gap-0.5">
          <span className="font-mono text-foreground">C</span>=class
          <HelpHint term="code_type" inline />
        </span>
        <span className="text-muted-foreground/40">·</span>
        <span className="inline-flex items-center gap-0.5">
          <span className="font-mono text-violet-400">T</span>=term
          <HelpHint term="term" inline />
        </span>
        <span className="text-muted-foreground/40">·</span>
        <span className="inline-flex items-center gap-0.5">
          <span className="font-mono text-orange-400">A</span>=action
          <HelpHint term="action" inline />
        </span>
      </div>
    </div>
  );
}

/**
 * One-time legend that decodes the 5 KindBadges (class/mtd/term/act/rule)
 * shown in search results. Renders once at the top of the result list so
 * the badges aren't a mystery — each entry has its own HelpHint.
 */
function KindBadgeLegend() {
  const items: { kind: SearchHitDTO["kind"]; term: string }[] = [
    { kind: "code_type",   term: "code_type" },
    { kind: "code_method", term: "code_method" },
    { kind: "term",        term: "term" },
    { kind: "action",      term: "action" },
    { kind: "rule",        term: "business_rule" },
  ];
  return (
    <div className="px-2 py-1 border-b border-border bg-muted/20 flex items-center gap-1.5 flex-wrap text-[9.5px] text-muted-foreground">
      <span className="text-muted-foreground/70">종류:</span>
      {items.map((it) => (
        <span key={it.kind} className="inline-flex items-center gap-0.5">
          <KindBadge kind={it.kind} />
          <HelpHint term={it.term} inline />
        </span>
      ))}
    </div>
  );
}
