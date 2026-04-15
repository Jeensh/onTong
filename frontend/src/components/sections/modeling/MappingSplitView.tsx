"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { GitCompare, AlertTriangle, Loader2, Plus, Search } from "lucide-react";
import {
  getCodeGraph,
  getOntologyTree,
  getMappings,
  addMapping,
  getMappingGaps,
  type CodeEntity,
  type DomainNode,
  type MappingEntry,
} from "@/lib/api/modeling";

const STATUS_BADGE: Record<string, string> = {
  draft: "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400",
  review: "bg-amber-100 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400",
  confirmed: "bg-green-100 dark:bg-green-950/40 text-green-700 dark:text-green-400",
};

function SearchableSelect({
  options,
  value,
  onChange,
  placeholder,
  renderOption,
}: {
  options: { id: string; label: string; sub?: string }[];
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  renderOption?: (o: { id: string; label: string; sub?: string }) => React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    if (!query) return options;
    const q = query.toLowerCase();
    return options.filter(
      (o) => o.label.toLowerCase().includes(q) || (o.sub && o.sub.toLowerCase().includes(q))
    );
  }, [options, query]);

  const selected = options.find((o) => o.id === value);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full mt-1 px-2 py-1.5 text-sm bg-background border border-border rounded text-left truncate"
      >
        {selected ? (
          <span className="font-mono text-xs">{selected.label}</span>
        ) : (
          <span className="text-muted-foreground text-xs">{placeholder}</span>
        )}
      </button>
      {open && (
        <div className="absolute z-50 mt-1 w-full bg-card border border-border rounded-lg shadow-lg max-h-64 overflow-hidden">
          <div className="p-2 border-b border-border">
            <div className="relative">
              <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
              <input
                type="text"
                autoFocus
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="검색..."
                className="w-full pl-7 pr-2 py-1 text-xs bg-background border border-border rounded"
              />
            </div>
          </div>
          <div className="max-h-48 overflow-auto">
            {filtered.length === 0 && (
              <p className="text-xs text-muted-foreground p-3 text-center">결과 없음</p>
            )}
            {filtered.map((o) => (
              <button
                key={o.id}
                type="button"
                onClick={() => {
                  onChange(o.id);
                  setOpen(false);
                  setQuery("");
                }}
                className={`w-full px-3 py-1.5 text-left hover:bg-muted/50 text-xs ${
                  o.id === value ? "bg-primary/10 text-primary" : ""
                }`}
              >
                {renderOption ? (
                  renderOption(o)
                ) : (
                  <>
                    <span className="font-mono">{o.label}</span>
                    {o.sub && <span className="text-muted-foreground ml-1">({o.sub})</span>}
                  </>
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function MappingSplitView({ repoId }: { repoId: string }) {
  const [codeEntities, setCodeEntities] = useState<CodeEntity[]>([]);
  const [domainNodes, setDomainNodes] = useState<DomainNode[]>([]);
  const [mappings, setMappings] = useState<MappingEntry[]>([]);
  const [gapsCount, setGapsCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Column search
  const [codeSearch, setCodeSearch] = useState("");
  const [domainSearch, setDomainSearch] = useState("");
  const [showUnmappedOnly, setShowUnmappedOnly] = useState(false);

  // Add mapping form
  const [showAddForm, setShowAddForm] = useState(false);
  const [selectedCode, setSelectedCode] = useState("");
  const [selectedDomain, setSelectedDomain] = useState("");
  const [owner, setOwner] = useState("");
  const [adding, setAdding] = useState(false);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [codeData, ontologyData, mappingData, gapsData] = await Promise.all([
        getCodeGraph(repoId),
        getOntologyTree(),
        getMappings(repoId),
        getMappingGaps(repoId),
      ]);
      setCodeEntities(codeData.entities);
      setDomainNodes(ontologyData.nodes);
      setMappings(mappingData.mappings);
      setGapsCount(gapsData.count);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [repoId]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  // Mapped code entity IDs
  const mappedCodes = useMemo(() => new Set(mappings.map((m) => m.code)), [mappings]);

  // Filtered code entities: only class/interface by default, + search + unmapped filter
  const filteredCode = useMemo(() => {
    let list = codeEntities.filter((e) => e.kind === "class" || e.kind === "interface");
    if (codeSearch) {
      const q = codeSearch.toLowerCase();
      list = list.filter((e) => e.name.toLowerCase().includes(q) || e.id.toLowerCase().includes(q));
    }
    if (showUnmappedOnly) {
      list = list.filter((e) => !mappedCodes.has(e.id));
    }
    return list;
  }, [codeEntities, codeSearch, showUnmappedOnly, mappedCodes]);

  // Filtered domain nodes
  const filteredDomain = useMemo(() => {
    if (!domainSearch) return domainNodes;
    const q = domainSearch.toLowerCase();
    return domainNodes.filter(
      (n) => n.name.toLowerCase().includes(q) || n.id.toLowerCase().includes(q)
    );
  }, [domainNodes, domainSearch]);

  // Searchable select options
  const codeOptions = useMemo(
    () =>
      codeEntities
        .filter((e) => e.kind === "class" || e.kind === "interface")
        .map((e) => ({ id: e.id, label: e.name, sub: e.kind })),
    [codeEntities]
  );
  const domainOptions = useMemo(
    () => domainNodes.map((n) => ({ id: n.id, label: n.name, sub: n.kind })),
    [domainNodes]
  );

  const handleAddMapping = async () => {
    if (!selectedCode || !selectedDomain || !owner.trim()) return;
    setAdding(true);
    setError(null);
    try {
      await addMapping(repoId, selectedCode, selectedDomain, owner.trim());
      setSelectedCode("");
      setSelectedDomain("");
      setOwner("");
      setShowAddForm(false);
      await fetchAll();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setAdding(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin mr-2" />
        Loading...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold mb-1">매핑 관리</h2>
          <p className="text-sm text-muted-foreground">
            코드 엔티티(클래스)와 도메인 프로세스(SCOR)를 연결합니다.
            매핑이 있어야 영향분석이 동작합니다.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {gapsCount > 0 && (
            <span className="inline-flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400 bg-amber-100 dark:bg-amber-950/40 px-2.5 py-1 rounded-full">
              <AlertTriangle className="h-3 w-3" />
              {gapsCount}개 미매핑
            </span>
          )}
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Plus className="h-3.5 w-3.5" />
            매핑 추가
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-950/20 p-3 text-sm text-red-700 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Add mapping form */}
      {showAddForm && (
        <div className="rounded-lg border border-border bg-card p-4 space-y-3">
          <p className="text-sm font-medium">새 매핑 추가</p>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-xs text-muted-foreground">코드 엔티티 (클래스)</label>
              <SearchableSelect
                options={codeOptions}
                value={selectedCode}
                onChange={setSelectedCode}
                placeholder="클래스 선택..."
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">도메인 노드</label>
              <SearchableSelect
                options={domainOptions}
                value={selectedDomain}
                onChange={setSelectedDomain}
                placeholder="SCOR 프로세스 선택..."
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">담당자</label>
              <input
                type="text"
                value={owner}
                onChange={(e) => setOwner(e.target.value)}
                placeholder="예: SCM팀"
                className="w-full mt-1 px-2 py-1.5 text-sm bg-background border border-border rounded"
              />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <button
              onClick={() => setShowAddForm(false)}
              className="px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground"
            >
              취소
            </button>
            <button
              onClick={handleAddMapping}
              disabled={adding || !selectedCode || !selectedDomain || !owner.trim()}
              className="inline-flex items-center gap-1 rounded-md bg-primary px-4 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {adding && <Loader2 className="h-3 w-3 animate-spin" />}
              추가
            </button>
          </div>
        </div>
      )}

      {/* Split view */}
      <div className="grid grid-cols-3 gap-4">
        {/* Left: Code Entities */}
        <div className="rounded-lg border border-border bg-card">
          <div className="px-3 py-2 border-b border-border bg-muted/30 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">코드 엔티티</span>
              <span className="text-xs text-muted-foreground">({filteredCode.length})</span>
            </div>
            <div className="relative">
              <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
              <input
                type="text"
                value={codeSearch}
                onChange={(e) => setCodeSearch(e.target.value)}
                placeholder="클래스 검색..."
                className="w-full pl-7 pr-2 py-1 text-xs bg-background border border-border rounded"
              />
            </div>
            <label className="flex items-center gap-1.5 text-[11px] text-muted-foreground cursor-pointer">
              <input
                type="checkbox"
                checked={showUnmappedOnly}
                onChange={(e) => setShowUnmappedOnly(e.target.checked)}
                className="rounded"
              />
              미매핑만 보기
            </label>
          </div>
          <div className="divide-y divide-border max-h-96 overflow-auto">
            {filteredCode.length === 0 && (
              <p className="text-xs text-muted-foreground p-4 text-center">결과 없음</p>
            )}
            {filteredCode.map((e) => (
              <div
                key={e.id}
                className={`px-3 py-1.5 ${mappedCodes.has(e.id) ? "" : "border-l-2 border-l-amber-400"}`}
              >
                <span className="text-xs font-mono">{e.name}</span>
                {!mappedCodes.has(e.id) && (
                  <span className="text-[10px] text-amber-500 ml-1">미매핑</span>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Center: Mappings */}
        <div className="rounded-lg border border-border bg-card">
          <div className="px-3 py-2 border-b border-border bg-muted/30">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">매핑 목록</span>
              <span className="text-xs text-muted-foreground">({mappings.length})</span>
            </div>
          </div>
          <div className="divide-y divide-border max-h-96 overflow-auto">
            {mappings.length === 0 && (
              <div className="p-4 text-center space-y-2">
                <p className="text-xs text-muted-foreground">매핑이 없습니다.</p>
                <p className="text-[11px] text-muted-foreground">
                  위의 &ldquo;매핑 추가&rdquo; 버튼으로 코드와 도메인을 연결하세요.
                </p>
              </div>
            )}
            {mappings.map((m, i) => (
              <div key={`${m.code}-${m.domain}-${i}`} className="px-3 py-2 space-y-1">
                <div className="text-xs space-y-0.5">
                  <p className="font-mono truncate" title={m.code}>
                    {m.code.split(".").pop()}
                  </p>
                  <p className="flex items-center gap-1 text-muted-foreground">
                    <GitCompare className="h-3 w-3 shrink-0" />
                    <span className="truncate" title={m.domain}>
                      {m.domain.split("/").pop()}
                    </span>
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-medium ${
                      Object.hasOwn(STATUS_BADGE, m.status) ? STATUS_BADGE[m.status] : STATUS_BADGE.draft
                    }`}
                  >
                    {m.status}
                  </span>
                  <span className="text-[10px] text-muted-foreground">{m.owner}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Domain Nodes */}
        <div className="rounded-lg border border-border bg-card">
          <div className="px-3 py-2 border-b border-border bg-muted/30 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">도메인 노드</span>
              <span className="text-xs text-muted-foreground">({filteredDomain.length})</span>
            </div>
            <div className="relative">
              <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
              <input
                type="text"
                value={domainSearch}
                onChange={(e) => setDomainSearch(e.target.value)}
                placeholder="도메인 노드 검색..."
                className="w-full pl-7 pr-2 py-1 text-xs bg-background border border-border rounded"
              />
            </div>
          </div>
          <div className="divide-y divide-border max-h-96 overflow-auto">
            {filteredDomain.length === 0 && (
              <p className="text-xs text-muted-foreground p-4 text-center">결과 없음</p>
            )}
            {filteredDomain.map((n) => (
              <div key={n.id} className="px-3 py-1.5">
                <span className="text-xs">{n.name}</span>
                <span className="text-[10px] text-muted-foreground ml-1">({n.kind})</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
