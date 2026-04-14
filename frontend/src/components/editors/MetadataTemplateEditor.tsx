"use client";

import { useCallback, useEffect, useState } from "react";
import { ChevronDown, ChevronRight, FileText, Loader2, Plus, X } from "lucide-react";
import { useWorkspaceStore } from "@/lib/workspace/useWorkspaceStore";
import { fetchTemplates } from "@/lib/api/metadata";
import type { MetadataTemplates } from "@/types";
import { toast } from "sonner";

interface MetadataTemplateEditorProps {
  tabId: string;
}

// ── Domain-Process Tree ──��─────────────────────────────────────────

function DomainTree({
  templates,
  onRefresh,
}: {
  templates: MetadataTemplates;
  onRefresh: () => void;
}) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [domainDocCount, setDomainDocCount] = useState<Record<string, number>>({});
  const [newDomain, setNewDomain] = useState("");
  const [newProcess, setNewProcess] = useState<Record<string, string>>({});
  const openTab = useWorkspaceStore((s) => s.openTab);

  const toggleDomain = useCallback((domain: string) => {
    setExpanded((prev) => {
      const next = prev === domain ? null : domain;
      if (next && domainDocCount[domain] === undefined) {
        fetch(`/api/metadata/files-by-tag?field=domain&value=${encodeURIComponent(domain)}&offset=0&limit=0`)
          .then((r) => r.json())
          .then((data: { total: number }) => {
            setDomainDocCount((prev) => ({ ...prev, [domain]: data.total }));
          })
          .catch(() => {});
      }
      return next;
    });
  }, [domainDocCount]);

  const handleAddDomain = useCallback(async () => {
    const name = newDomain.trim();
    if (!name) return;
    try {
      const res = await fetch("/api/metadata/templates/domain", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, processes: [] }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed");
      }
      setNewDomain("");
      toast.success(`도메인 "${name}" 추가`);
      onRefresh();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "추가 실패");
    }
  }, [newDomain, onRefresh]);

  const handleRemoveDomain = useCallback(async (domain: string) => {
    if (!confirm(`"${domain}" 도메인과 하위 프로세스를 모두 삭제합니다.`)) return;
    try {
      const res = await fetch(`/api/metadata/templates/domain/${encodeURIComponent(domain)}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("Failed");
      toast.success(`도메인 "${domain}" 삭제`);
      if (expanded === domain) setExpanded(null);
      onRefresh();
    } catch {
      toast.error("삭제 실패");
    }
  }, [expanded, onRefresh]);

  const handleAddProcess = useCallback(async (domain: string) => {
    const name = (newProcess[domain] || "").trim();
    if (!name) return;
    try {
      const res = await fetch(`/api/metadata/templates/domain/${encodeURIComponent(domain)}/process`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed");
      }
      setNewProcess((prev) => ({ ...prev, [domain]: "" }));
      toast.success(`프로세스 "${name}" 추가`);
      onRefresh();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "추가 실패");
    }
  }, [newProcess, onRefresh]);

  const handleRemoveProcess = useCallback(async (domain: string, process: string) => {
    try {
      const res = await fetch(
        `/api/metadata/templates/domain/${encodeURIComponent(domain)}/process/${encodeURIComponent(process)}`,
        { method: "DELETE" }
      );
      if (!res.ok) throw new Error("Failed");
      toast.success(`프로세스 "${process}" 삭제`);
      onRefresh();
    } catch {
      toast.error("삭제 실패");
    }
  }, [onRefresh]);

  const domains = Object.keys(templates.domain_processes).sort();

  return (
    <div>
      <h3 className="text-sm font-semibold mb-2">Domain / Process</h3>

      <div className="border rounded-md divide-y">
        {domains.map((domain) => {
          const processes = templates.domain_processes[domain] || [];
          const isExpanded = expanded === domain;
          const docCount = domainDocCount[domain];

          return (
            <div key={domain}>
              {/* Domain row */}
              <div className="flex items-center px-3 py-2 hover:bg-muted/50 group">
                <button
                  type="button"
                  className="p-0.5 mr-1.5 rounded hover:bg-muted-foreground/20"
                  onClick={() => toggleDomain(domain)}
                >
                  {isExpanded ? (
                    <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                  )}
                </button>
                <span
                  className="flex-1 text-sm font-medium cursor-pointer"
                  onClick={() => toggleDomain(domain)}
                >
                  {domain}
                </span>
                <span className="text-[10px] text-muted-foreground mr-2">
                  {processes.length} process · {docCount !== undefined ? docCount : "?"} docs
                </span>
                <button
                  onClick={() => handleRemoveDomain(domain)}
                  className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive transition-opacity"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>

              {/* Expanded: processes */}
              {isExpanded && (
                <div className="bg-muted/20 border-t">
                  {processes.map((proc) => (
                    <ProcessRow
                      key={proc}
                      domain={domain}
                      process={proc}
                      onRemove={() => handleRemoveProcess(domain, proc)}
                      onOpenFile={openTab}
                    />
                  ))}

                  {processes.length === 0 && (
                    <div className="px-8 py-2 text-xs text-muted-foreground">
                      프로세스 없음
                    </div>
                  )}

                  {/* Add process input */}
                  <div className="flex gap-1.5 px-8 py-2">
                    <input
                      value={newProcess[domain] || ""}
                      onChange={(e) => setNewProcess((prev) => ({ ...prev, [domain]: e.target.value }))}
                      onKeyDown={(e) => e.key === "Enter" && !e.nativeEvent.isComposing && handleAddProcess(domain)}
                      placeholder="새 프로세스..."
                      className="flex-1 text-xs border rounded px-2 py-1 bg-background"
                    />
                    <button
                      onClick={() => handleAddProcess(domain)}
                      disabled={!(newProcess[domain] || "").trim()}
                      className="px-2 py-1 text-xs rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                    >
                      <Plus className="h-3 w-3" />
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}

        {domains.length === 0 && (
          <div className="px-3 py-4 text-xs text-muted-foreground text-center">
            도메인 없음
          </div>
        )}
      </div>

      {/* Add domain input */}
      <div className="flex gap-1.5 mt-2">
        <input
          value={newDomain}
          onChange={(e) => setNewDomain(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.nativeEvent.isComposing && handleAddDomain()}
          placeholder="새 도메인 입력..."
          className="flex-1 text-xs border rounded px-2 py-1 bg-background"
        />
        <button
          onClick={handleAddDomain}
          disabled={!newDomain.trim()}
          className="px-2 py-1 text-xs rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          <Plus className="h-3 w-3" />
        </button>
      </div>
    </div>
  );
}

// ── Process Row (expandable �� files) ───────────────────────────────

const EDITOR_FILE_LIMIT = 20;

function ProcessRow({
  domain,
  process,
  onRemove,
  onOpenFile,
}: {
  domain: string;
  process: string;
  onRemove: () => void;
  onOpenFile: (path: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [files, setFiles] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  const loadFiles = useCallback((offset: number) => {
    setLoading(true);
    fetch(`/api/metadata/files-by-tag?field=process&value=${encodeURIComponent(process)}&offset=${offset}&limit=${EDITOR_FILE_LIMIT}`)
      .then((r) => r.json())
      .then((data: { files: string[]; total: number }) => {
        setFiles((prev) => offset === 0 ? data.files : [...prev, ...data.files]);
        setTotal(data.total);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [process]);

  const toggle = () => {
    if (!expanded) loadFiles(0);
    setExpanded(!expanded);
  };

  return (
    <div>
      <div className="flex items-center px-6 py-1.5 hover:bg-muted/50 group">
        <button
          type="button"
          className="p-0.5 mr-1 rounded hover:bg-muted-foreground/20"
          onClick={toggle}
        >
          {expanded ? (
            <ChevronDown className="h-3 w-3 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-3 w-3 text-muted-foreground" />
          )}
        </button>
        <span className="flex-1 text-xs cursor-pointer" onClick={toggle}>
          {process}
        </span>
        {total > 0 && (
          <span className="text-[10px] text-muted-foreground mr-2">
            {total} docs
          </span>
        )}
        <button
          onClick={onRemove}
          className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive transition-opacity"
        >
          <X className="h-3 w-3" />
        </button>
      </div>

      {expanded && (
        <div className="pl-12 py-1">
          {loading && files.length === 0 ? (
            <div className="text-[10px] text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin inline mr-1" />
              로딩 중...
            </div>
          ) : files.length === 0 ? (
            <div className="text-[10px] text-muted-foreground py-0.5">문서 없음</div>
          ) : (
            <>
              {files.map((path) => (
                <button
                  key={path}
                  className="flex items-center gap-1 w-full text-left px-1 py-0.5 text-[11px] text-blue-600 dark:text-blue-400 hover:underline rounded hover:bg-muted/50"
                  onClick={() => onOpenFile(path)}
                >
                  <FileText className="h-3 w-3 shrink-0 text-muted-foreground" />
                  {path}
                </button>
              ))}
              {files.length < total && (
                <button
                  onClick={() => loadFiles(files.length)}
                  disabled={loading}
                  className="text-[11px] text-primary hover:underline px-1 py-0.5"
                >
                  {loading ? "로딩 중..." : `더보기 (${total - files.length}건 남음)`}
                </button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ── Tag Presets Section ─────────────────────────────────────────────

function TagPresetsSection({
  presets,
  onRefresh,
}: {
  presets: string[];
  onRefresh: () => void;
}) {
  const [input, setInput] = useState("");

  const handleAdd = async () => {
    const v = input.trim();
    if (!v) return;
    try {
      const res = await fetch("/api/metadata/templates/tag-preset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value: v }),
      });
      if (!res.ok) throw new Error("Failed");
      setInput("");
      toast.success(`태그 "${v}" 추가`);
      onRefresh();
    } catch {
      toast.error("추가 실패");
    }
  };

  const handleRemove = async (value: string) => {
    try {
      const res = await fetch(`/api/metadata/templates/tag-preset/${encodeURIComponent(value)}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("Failed");
      toast.success(`태그 "${value}" 삭제`);
      onRefresh();
    } catch {
      toast.error("삭제 실패");
    }
  };

  return (
    <div>
      <h3 className="text-sm font-semibold mb-2">Tag Presets (자주 사용하는 태그)</h3>
      <div className="flex flex-wrap gap-1.5 mb-2">
        {presets.map((tag) => (
          <span
            key={tag}
            className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-md bg-muted border"
          >
            {tag}
            <button
              onClick={() => handleRemove(tag)}
              className="text-muted-foreground hover:text-destructive"
            >
              <X className="h-3 w-3" />
            </button>
          </span>
        ))}
        {presets.length === 0 && (
          <span className="text-xs text-muted-foreground">항목 없음</span>
        )}
      </div>
      <div className="flex gap-1.5">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.nativeEvent.isComposing && handleAdd()}
          placeholder="새 태그 입력..."
          className="flex-1 text-xs border rounded px-2 py-1 bg-background"
        />
        <button
          onClick={handleAdd}
          disabled={!input.trim()}
          className="px-2 py-1 text-xs rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          <Plus className="h-3 w-3" />
        </button>
      </div>
    </div>
  );
}

// ── Main Component ���─────────────────────────────────────────────────

function TagHealthSection() {
  const [similarGroups, setSimilarGroups] = useState<{ tag: string; distance: number; count: number }[][]>([]);
  const [orphans, setOrphans] = useState<{ name: string; count: number }[]>([]);
  const [loading, setLoading] = useState(false);
  const [merging, setMerging] = useState<string | null>(null);

  const loadHealth = useCallback(() => {
    setLoading(true);
    Promise.all([
      fetch("/api/metadata/tags/similar-groups?threshold=0.20").then((r) => r.json()),
      fetch("/api/metadata/tags/orphans?min_docs=1").then((r) => r.json()),
    ])
      .then(([groups, orphanData]) => {
        setSimilarGroups(groups.groups || []);
        setOrphans(orphanData.orphans || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const handleMerge = useCallback(async (source: string, target: string) => {
    if (!confirm(`"${source}" → "${target}" 로 병합합니다. 관련 문서가 모두 업데이트됩니다.`)) return;
    setMerging(source);
    try {
      const res = await fetch(`/api/metadata/tags/merge?source=${encodeURIComponent(source)}&target=${encodeURIComponent(target)}`, {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        toast.success(`"${source}" → "${target}" 병합 완료 (${data.updated_documents}건 업데이트)`);
        loadHealth();
      }
    } catch {
      toast.error("병합 실패");
    }
    setMerging(null);
  }, [loadHealth]);

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold">태그 건강도</h3>
        <button
          onClick={loadHealth}
          disabled={loading}
          className="text-xs text-primary hover:underline disabled:opacity-50"
        >
          {loading ? "분석 중..." : "분석 실행"}
        </button>
      </div>

      {similarGroups.length > 0 && (
        <div className="mb-3">
          <span className="text-xs text-muted-foreground block mb-1">
            유사 태그 그룹 ({similarGroups.length}건) — 병합을 권장합니다
          </span>
          <div className="space-y-2">
            {similarGroups.map((group, i) => (
              <div key={i} className="border rounded p-2 text-xs">
                <div className="flex flex-wrap gap-1 mb-1.5">
                  {group.map((t) => (
                    <span key={t.tag} className="px-1.5 py-0.5 rounded bg-muted border">
                      {t.tag} <span className="text-muted-foreground">({t.count}건)</span>
                    </span>
                  ))}
                </div>
                {group.length >= 2 && (
                  <div className="flex gap-1 flex-wrap">
                    {group.slice(1).map((source) => {
                      const target = group[0];
                      return (
                        <button
                          key={source.tag}
                          onClick={() => handleMerge(source.tag, target.tag)}
                          disabled={merging === source.tag}
                          className="text-[11px] text-primary hover:underline disabled:opacity-50"
                        >
                          {merging === source.tag ? "병합 중..." : `"${source.tag}" → "${target.tag}"`}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {orphans.length > 0 && (
        <div>
          <span className="text-xs text-muted-foreground block mb-1">
            고아 태그 ({orphans.length}건) — 1건 이하 문서에서만 사용
          </span>
          <div className="flex flex-wrap gap-1">
            {orphans.slice(0, 20).map((t) => (
              <span key={t.name} className="px-1.5 py-0.5 text-xs rounded bg-yellow-50 border border-yellow-200 text-yellow-700 dark:bg-yellow-900/20 dark:border-yellow-800 dark:text-yellow-400">
                {t.name} ({t.count})
              </span>
            ))}
            {orphans.length > 20 && (
              <span className="text-[11px] text-muted-foreground">+{orphans.length - 20}건 더</span>
            )}
          </div>
        </div>
      )}

      {!loading && similarGroups.length === 0 && orphans.length === 0 && (
        <p className="text-xs text-muted-foreground">&quot;분석 실행&quot;을 클릭하면 유사 태그와 고아 태그를 검출합니다.</p>
      )}
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────

export function MetadataTemplateEditor({ tabId: _tabId }: MetadataTemplateEditorProps) {
  const [templates, setTemplates] = useState<MetadataTemplates | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    fetchTemplates()
      .then((t) => { setTemplates(t); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin mr-2" />
        <p className="text-sm">로딩 중...</p>
      </div>
    );
  }

  if (!templates) {
    return (
      <div className="flex items-center justify-center h-full text-destructive">
        <p className="text-sm">템플릿 로드 실패</p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6">
      <div>
        <h2 className="text-lg font-bold">메타데이터 템플릿 관리</h2>
        <p className="text-sm text-muted-foreground mt-1">
          도메인을 클릭하면 하위 프로세스와 문서를 확인할 수 있습니다.
        </p>
      </div>

      <div className="border rounded-lg p-4 space-y-5">
        <DomainTree templates={templates} onRefresh={load} />

        <div className="border-t" />

        <TagPresetsSection presets={templates.tag_presets} onRefresh={load} />

        <div className="border-t" />

        <TagHealthSection />
      </div>
    </div>
  );
}
