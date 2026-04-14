"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  Sparkles,
  MessageSquareQuote,
  CheckCircle2,
  AlertCircle,
  ArrowUp,
  Link2,
  ArrowRight,
  ArrowLeft,
  Network,
  Loader2,
  X,
  FilePlus,
  GitBranch,
} from "lucide-react";
import { useWorkspaceStore } from "@/lib/workspace/useWorkspaceStore";
import { toast } from "sonner";
import { fetchTemplates, searchTagsWithCount, checkSimilarTags, searchPaths } from "@/lib/api/metadata";
import type { DocumentMetadata, MetadataTemplates } from "@/types";
import { TagInput } from "./metadata/TagInput";
import { DomainSelect } from "./metadata/DomainSelect";
import { AutoTagButton } from "./metadata/AutoTagButton";
import { VersionTimeline } from "./VersionTimeline";

interface ConfidenceData {
  score: number;
  tier: string;
  stale: boolean;
  stale_months: number;
  signals: Record<string, number>;
  citation_count: number;
  newer_alternatives: Array<{
    path: string;
    title: string;
    confidence_score: number;
    confidence_tier: string;
  }>;
}

interface FeedbackData {
  verified_count: number;
  needs_update_count: number;
  last_verified_at: number;
  last_verified_by: string;
}

interface LineageRef {
  path: string;
  title: string;
  status: string;
  updated: string;
}

interface LineageData {
  path: string;
  supersedes: LineageRef | null;
  superseded_by: LineageRef | null;
  related: LineageRef[];
}

interface BacklinkMap {
  forward: Record<string, string[]>;
  backward: Record<string, string[]>;
}

interface RelatedDoc {
  path: string;
  title: string;
  snippet: string;
  similarity: number;
  confidence_score: number;
  confidence_tier: string;
  relationship: string;
}

const SIGNAL_DEFS = [
  { key: "freshness", label: "최신성", weight: 25, desc: "최근 수정일 기준" },
  { key: "status", label: "문서 상태", weight: 25, desc: "approved/draft/deprecated" },
  { key: "metadata_completeness", label: "메타데이터", weight: 15, desc: "domain, process, tags, 작성자" },
  { key: "backlinks", label: "역참조", weight: 10, desc: "다른 문서에서 참조 횟수" },
  { key: "owner_activity", label: "작성자 활동", weight: 10, desc: "최근 90일 편집 이력" },
  { key: "user_feedback", label: "사용자 피드백", weight: 15, desc: "확인/수정요청 비율" },
];

function getApiBase() {
  return typeof window !== "undefined" && window.location.hostname === "localhost"
    ? "http://localhost:8001" : "";
}

function fileName(path: string): string {
  return path.split("/").pop()?.replace(".md", "") ?? path;
}

function formatDate(iso: string): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("ko-KR", {
      year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit",
    });
  } catch { return iso; }
}

function timeAgo(ts: number): string {
  if (!ts) return "";
  const diff = (Date.now() / 1000) - ts;
  if (diff < 60) return "방금 전";
  if (diff < 3600) return `${Math.floor(diff / 60)}분 전`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
  return `${Math.floor(diff / 86400)}일 전`;
}

export interface DocumentInfoDrawerProps {
  open: boolean;
  activeTab: string;
  onTabChange: (tab: string) => void;
  onClose: () => void;
  filePath: string;
  // Metadata tab
  metadata: DocumentMetadata;
  content: string;
  onMetadataChange: (meta: DocumentMetadata) => void;
  // Trust tab (shared state from parent)
  confidenceData: ConfidenceData | null;
  feedbackData: FeedbackData | null;
  onConfidenceUpdate: (data: ConfidenceData) => void;
  onFeedbackUpdate: (data: FeedbackData) => void;
  // Connection counts callback
  onConnectionCountChange: (total: number) => void;
  // Dirty state
  isDirty?: boolean;
  onSave?: () => void;
}

export function DocumentInfoDrawer({
  open,
  activeTab,
  onTabChange,
  onClose,
  filePath,
  metadata,
  content,
  onMetadataChange,
  confidenceData,
  feedbackData,
  onConfidenceUpdate,
  onFeedbackUpdate,
  onConnectionCountChange,
  isDirty,
  onSave,
}: DocumentInfoDrawerProps) {
  const drawerRef = useRef<HTMLDivElement>(null);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  // Click outside closes drawer (but ignore clicks on the InfoBar toggle)
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      // If target was removed from DOM (e.g. dropdown item clicked then unmounted), ignore
      if (!document.body.contains(target)) return;
      // Ignore clicks inside the drawer itself
      if (drawerRef.current && drawerRef.current.contains(target)) return;
      // Ignore clicks on the InfoBar — its toggle handler manages open/close
      if (target.closest?.("[data-info-bar]")) return;
      onClose();
    };
    const timer = setTimeout(() => {
      document.addEventListener("mousedown", handler);
    }, 100);
    return () => {
      clearTimeout(timer);
      document.removeEventListener("mousedown", handler);
    };
  }, [open, onClose]);

  if (!open) return null;

  const tabs = [
    { id: "metadata", label: "메타데이터" },
    { id: "trust", label: "신뢰도" },
    { id: "connections", label: "연결 문서" },
  ];

  return (
    <div
      ref={drawerRef}
      className="absolute left-0 right-0 top-0 z-40 bg-background border-b shadow-lg max-h-[60vh] overflow-auto"
    >
      {/* Tab navigation */}
      <div className="flex items-center border-b px-3 sticky top-0 bg-background z-10">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={`px-3 py-2 text-xs font-medium border-b-2 transition-colors ${
              activeTab === tab.id
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab.label}
          </button>
        ))}
        <div className="flex-1" />
        <button onClick={onClose} className="p-1 text-muted-foreground hover:text-foreground">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Tab content */}
      <div className="p-3">
        {activeTab === "metadata" && (
          <MetadataTabContent
            metadata={metadata}
            content={content}
            onChange={onMetadataChange}
            filePath={filePath}
            isDirty={isDirty}
            onSave={onSave}
          />
        )}
        {activeTab === "trust" && (
          <TrustTabContent
            filePath={filePath}
            data={confidenceData}
            feedback={feedbackData}
            onConfidenceUpdate={onConfidenceUpdate}
            onFeedbackUpdate={onFeedbackUpdate}
          />
        )}
        {activeTab === "connections" && (
          <ConnectionsTabContent
            filePath={filePath}
            onCountChange={onConnectionCountChange}
          />
        )}
      </div>
    </div>
  );
}

// ---- Create New Version Button ----
function CreateNewVersionButton({ filePath }: { filePath: string }) {
  const [showDialog, setShowDialog] = useState(false);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);
  const openTab = useWorkspaceStore((s) => s.openTab);
  const inputRef = useRef<HTMLInputElement>(null);

  const suggestName = useCallback(() => {
    const name = filePath.split("/").pop()?.replace(".md", "") ?? "";
    // Try to increment version: v1→v2, -v1→-v2, etc.
    const vMatch = name.match(/^(.*?)[-_]?v(\d+)$/i);
    if (vMatch) return `${vMatch[1]}-v${parseInt(vMatch[2]) + 1}.md`;
    return `${name}-v2.md`;
  }, [filePath]);

  const handleOpen = () => {
    setNewName(suggestName());
    setShowDialog(true);
    setTimeout(() => inputRef.current?.select(), 50);
  };

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    const folder = filePath.includes("/") ? filePath.substring(0, filePath.lastIndexOf("/")) : "";
    const fileName = newName.endsWith(".md") ? newName : `${newName}.md`;
    const newPath = folder ? `${folder}/${fileName}` : fileName;

    try {
      const res = await fetch("/api/wiki/create-new-version", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ old_path: filePath, new_path: newPath }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `HTTP ${res.status}`);
      }
      toast.success(`새 버전 "${fileName}" 생성됨`);
      setShowDialog(false);
      openTab(newPath);
    } catch (err) {
      toast.error("생성 실패", { description: (err as Error).message, duration: 5000 });
    } finally {
      setCreating(false);
    }
  };

  return (
    <>
      <button
        onClick={handleOpen}
        className="flex items-center gap-1.5 text-xs text-primary hover:text-primary/80 font-medium py-1"
      >
        <FilePlus className="h-3.5 w-3.5" />
        새 버전 작성
      </button>

      {showDialog && (
        <div className="rounded-md border bg-muted/50 p-3 space-y-2">
          <p className="text-[11px] text-muted-foreground">
            현재 문서의 새 버전을 생성합니다. 메타데이터(domain, tags 등)가 자동 상속됩니다.
          </p>
          <input
            ref={inputRef}
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") handleCreate(); if (e.key === "Escape") setShowDialog(false); }}
            placeholder="새 파일명.md"
            className="h-7 w-full rounded-md border bg-background px-2 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
          />
          <div className="flex gap-2">
            <button
              onClick={handleCreate}
              disabled={creating || !newName.trim()}
              className="h-6 px-3 rounded-md bg-primary text-primary-foreground text-[11px] font-medium hover:bg-primary/90 disabled:opacity-50"
            >
              {creating ? "생성 중..." : "생성"}
            </button>
            <button
              onClick={() => setShowDialog(false)}
              className="h-6 px-3 rounded-md border text-[11px] hover:bg-muted"
            >
              취소
            </button>
          </div>
        </div>
      )}
    </>
  );
}

// ---- Path Field (single-value with autocomplete + keyboard nav) ----
function PathField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  const [input, setInput] = useState(value || "");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [open, setOpen] = useState(false);
  const [highlightIdx, setHighlightIdx] = useState(-1);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const containerRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => { setInput(value || ""); }, [value]);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const handleInput = (v: string) => {
    setInput(v);
    setHighlightIdx(-1);
    clearTimeout(debounceRef.current);
    if (!v.trim()) { setSuggestions([]); setOpen(false); return; }
    debounceRef.current = setTimeout(async () => {
      const results = await searchPaths(v, 8);
      setSuggestions(results);
      setHighlightIdx(results.length > 0 ? 0 : -1);
      setOpen(results.length > 0);
    }, 200);
  };

  const select = (path: string) => {
    setInput(path);
    onChange(path);
    setOpen(false);
    setHighlightIdx(-1);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!open || suggestions.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightIdx((prev) => (prev + 1) % suggestions.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightIdx((prev) => (prev - 1 + suggestions.length) % suggestions.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (highlightIdx >= 0 && highlightIdx < suggestions.length) {
        select(suggestions[highlightIdx]);
      }
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  // Scroll highlighted item into view
  useEffect(() => {
    if (highlightIdx < 0 || !listRef.current) return;
    const item = listRef.current.children[highlightIdx] as HTMLElement;
    item?.scrollIntoView({ block: "nearest" });
  }, [highlightIdx]);

  const handleBlur = () => {
    setTimeout(() => {
      if (input !== value) onChange(input);
    }, 150);
  };

  const clear = () => {
    setInput("");
    onChange("");
  };

  return (
    <div ref={containerRef} className="relative">
      <span className="text-xs text-muted-foreground mb-1 block">{label}</span>
      <div className="flex items-center gap-1">
        <input
          value={input}
          onChange={(e) => handleInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => input.trim() && suggestions.length > 0 && setOpen(true)}
          onBlur={handleBlur}
          placeholder="문서 경로..."
          className="h-7 w-full rounded-md border bg-background px-2 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
        />
        {input && (
          <button onClick={clear} className="text-muted-foreground hover:text-foreground p-0.5">
            <X className="h-3 w-3" />
          </button>
        )}
      </div>
      {open && suggestions.length > 0 && (
        <div ref={listRef} className="absolute z-50 mt-1 w-full max-h-40 overflow-y-auto rounded-md border bg-popover shadow-md">
          {suggestions.map((s, i) => (
            <button
              key={s}
              onMouseDown={() => select(s)}
              className={`w-full text-left px-2 py-1 text-xs truncate ${
                i === highlightIdx ? "bg-accent text-accent-foreground" : "hover:bg-accent"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ---- Metadata Tab ----
function MetadataTabContent({
  metadata,
  content,
  onChange,
  filePath,
  isDirty,
  onSave,
}: {
  metadata: DocumentMetadata;
  content: string;
  onChange: (meta: DocumentMetadata) => void;
  filePath?: string;
  isDirty?: boolean;
  onSave?: () => void;
}) {
  const [templates, setTemplates] = useState<MetadataTemplates>({
    domain_processes: {},
    tag_presets: [],
  });

  useEffect(() => {
    fetchTemplates().then(setTemplates).catch(() => {});
  }, []);

  const domainOptions = useMemo(
    () => Object.keys(templates.domain_processes).sort(),
    [templates]
  );
  const processOptions = useMemo(() => {
    if (!metadata.domain) return [];
    return templates.domain_processes[metadata.domain] || [];
  }, [metadata.domain, templates]);

  const updateField = useCallback(
    <K extends keyof DocumentMetadata>(key: K, value: DocumentMetadata[K]) => {
      onChange({ ...metadata, [key]: value });
    },
    [metadata, onChange]
  );

  const handleAutoAccept = useCallback(
    (updates: Partial<DocumentMetadata>) => {
      onChange({ ...metadata, ...updates });
    },
    [metadata, onChange]
  );

  return (
    <div className="space-y-3 text-xs">
      <div className="flex items-center gap-4 flex-wrap">
        <DomainSelect
          label="Domain"
          value={metadata.domain}
          options={domainOptions}
          onChange={(v) => {
            if (v !== metadata.domain) {
              onChange({ ...metadata, domain: v, process: "" });
            } else {
              updateField("domain", v);
            }
          }}
        />
        <DomainSelect
          label="Process"
          value={metadata.process}
          options={processOptions}
          onChange={(v) => updateField("process", v)}
        />
      </div>

      <div>
        <span className="text-xs text-muted-foreground mb-1 block">Tags</span>
        <TagInput
          tags={metadata.tags}
          suggestions={templates.tag_presets}
          onSearchWithCount={searchTagsWithCount}
          onCheckSimilar={checkSimilarTags}
          onChange={(tags) => updateField("tags", tags)}
        />
      </div>

      <div className="flex items-center gap-4 flex-wrap">
        <div>
          <span className="text-xs text-muted-foreground mb-1 block">Status</span>
          <select
            value={metadata.status || ""}
            onChange={(e) => updateField("status", e.target.value as DocumentMetadata["status"])}
            className="h-7 rounded-md border bg-background px-2 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="draft">Draft</option>
            <option value="approved">Approved</option>
            <option value="deprecated">Deprecated</option>
          </select>
        </div>
      </div>

      <div>
        <span className="text-xs text-muted-foreground mb-1 block">관련 문서</span>
        <TagInput
          tags={metadata.related}
          onSearch={searchPaths}
          onChange={(related) => updateField("related", related)}
          placeholder="문서 경로 입력..."
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <PathField
          label="이전 버전 (supersedes)"
          value={metadata.supersedes}
          onChange={(v) => updateField("supersedes", v)}
        />
        <PathField
          label="새 버전 (superseded_by)"
          value={metadata.superseded_by}
          onChange={(v) => updateField("superseded_by", v)}
        />
      </div>

      {filePath && !metadata.superseded_by && (
        <CreateNewVersionButton filePath={filePath} />
      )}

      <div className="flex items-center gap-2">
        <AutoTagButton
          content={content}
          currentMetadata={metadata}
          onAccept={handleAutoAccept}
          filePath={filePath}
        />
        <div className="flex-1" />
        {isDirty && onSave && (
          <button
            onClick={onSave}
            className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded hover:bg-muted"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-amber-500 animate-pulse" />
            <span>저장</span>
            <kbd className="hidden sm:inline text-[10px] text-muted-foreground/60 ml-0.5">⌘S</kbd>
          </button>
        )}
      </div>

      {(metadata.created || metadata.created_by || metadata.updated || metadata.updated_by) && (
        <div className="flex items-center gap-4 flex-wrap text-[11px] text-muted-foreground pt-2 border-t border-border/50">
          {metadata.created_by && <span>작성자: <span className="text-foreground/70">{metadata.created_by}</span></span>}
          {metadata.created && <span>생성: <span className="text-foreground/70">{formatDate(metadata.created)}</span></span>}
          {metadata.updated_by && <span>최종 수정자: <span className="text-foreground/70">{metadata.updated_by}</span></span>}
          {metadata.updated && <span>최종 수정: <span className="text-foreground/70">{formatDate(metadata.updated)}</span></span>}
        </div>
      )}
    </div>
  );
}

// ---- Trust Tab ----
function TrustTabContent({
  filePath,
  data,
  feedback,
  onConfidenceUpdate,
  onFeedbackUpdate,
}: {
  filePath: string;
  data: ConfidenceData | null;
  feedback: FeedbackData | null;
  onConfidenceUpdate: (d: ConfidenceData) => void;
  onFeedbackUpdate: (d: FeedbackData) => void;
}) {
  const openTab = useWorkspaceStore((s) => s.openTab);
  const [feedbackLoading, setFeedbackLoading] = useState(false);

  const submitFeedback = useCallback(async (action: "verified" | "needs_update") => {
    setFeedbackLoading(true);
    try {
      const base = getApiBase();
      const res = await fetch(`${base}/api/wiki/feedback/${encodeURIComponent(filePath)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      if (res.ok) {
        const result = await res.json();
        onFeedbackUpdate(result.feedback);
        const confRes = await fetch(`${base}/api/wiki/confidence/${encodeURIComponent(filePath)}`);
        if (confRes.ok) {
          const conf = await confRes.json();
          if (conf && typeof conf.score === "number") onConfidenceUpdate(conf);
        }
      }
    } catch {}
    setFeedbackLoading(false);
  }, [filePath, onConfidenceUpdate, onFeedbackUpdate]);

  if (!data) {
    return <div className="text-xs text-muted-foreground py-2">신뢰도 데이터를 불러오는 중...</div>;
  }

  return (
    <div className="space-y-3 text-xs">
      {/* Signal breakdown */}
      <div>
        <div className="font-semibold mb-2 text-foreground">
          신뢰도 {data.score}점 ({data.tier === "high" ? "높음" : data.tier === "medium" ? "중간" : "낮음"})
        </div>
        <div className="space-y-1.5">
          {SIGNAL_DEFS.map(({ key, label, weight, desc }) => {
            const val = data.signals[key] ?? 0;
            return (
              <div key={key}>
                <div className="flex items-center justify-between">
                  <span className="text-foreground">
                    {label} <span className="text-muted-foreground">({weight}%)</span>
                  </span>
                  <span className={`font-mono font-medium ${
                    val >= 70 ? "text-green-600 dark:text-green-400"
                      : val >= 40 ? "text-yellow-600 dark:text-yellow-400"
                      : "text-gray-500"
                  }`}>
                    {Math.round(val)}
                  </span>
                </div>
                <div className="flex items-center gap-1 mt-0.5">
                  <div className="flex-1 h-1 rounded-full bg-muted overflow-hidden">
                    <div
                      className={`h-full rounded-full ${
                        val >= 70 ? "bg-green-500" : val >= 40 ? "bg-yellow-500" : "bg-gray-400"
                      }`}
                      style={{ width: `${Math.min(val, 100)}%` }}
                    />
                  </div>
                  <span className="text-[10px] text-muted-foreground w-24 text-right">{desc}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {data.citation_count > 0 && (
        <div className="flex items-center gap-1 text-muted-foreground">
          <MessageSquareQuote className="h-3 w-3" />
          AI 답변에서 {data.citation_count}회 인용됨
        </div>
      )}

      {/* Stale warning */}
      {data.stale && (
        <div className="flex items-center gap-1.5 px-3 py-2 bg-amber-50 dark:bg-amber-950/20 text-amber-700 dark:text-amber-400 rounded">
          <AlertTriangle className="h-3 w-3 shrink-0" />
          <span>{data.stale_months}개월 이상 수정되지 않았습니다</span>
        </div>
      )}

      {/* Newer alternatives */}
      {data.newer_alternatives && data.newer_alternatives.length > 0 && (
        <div className="px-3 py-2 bg-blue-50 dark:bg-blue-950/20 text-blue-700 dark:text-blue-300 rounded">
          <div className="flex items-center gap-1.5 mb-1">
            <Sparkles className="h-3 w-3 shrink-0" />
            <span>이 주제의 최신 문서:</span>
          </div>
          <div className="space-y-0.5 pl-4">
            {data.newer_alternatives.map((alt) => (
              <div key={alt.path} className="flex items-center gap-1.5">
                <span className={`inline-block h-1.5 w-1.5 rounded-full shrink-0 ${
                  alt.confidence_tier === "high" ? "bg-green-500"
                    : alt.confidence_tier === "medium" ? "bg-yellow-500" : "bg-gray-400"
                }`} />
                <button
                  onClick={() => openTab(alt.path)}
                  className="text-blue-600 dark:text-blue-400 hover:underline truncate max-w-[200px]"
                >
                  {alt.title}
                </button>
                <span className="text-[10px] text-blue-500/70">신뢰도 {alt.confidence_score}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Feedback section */}
      <div className="border-t pt-2">
        <div className="font-medium mb-1.5">사용자 피드백</div>
        <div className="flex items-center gap-2">
          <button
            disabled={feedbackLoading}
            onClick={() => submitFeedback("verified")}
            className="inline-flex items-center gap-1 rounded px-2 py-1 text-green-700 dark:text-green-400 bg-green-50 dark:bg-green-900/20 hover:bg-green-100 dark:hover:bg-green-900/40 transition-colors disabled:opacity-50"
          >
            <CheckCircle2 className="h-3 w-3" />
            확인했음
          </button>
          <button
            disabled={feedbackLoading}
            onClick={() => submitFeedback("needs_update")}
            className="inline-flex items-center gap-1 rounded px-2 py-1 text-orange-700 dark:text-orange-400 bg-orange-50 dark:bg-orange-900/20 hover:bg-orange-100 dark:hover:bg-orange-900/40 transition-colors disabled:opacity-50"
          >
            <AlertCircle className="h-3 w-3" />
            수정 필요
          </button>
        </div>
        {feedback && (feedback.verified_count > 0 || feedback.needs_update_count > 0) && (
          <div className="text-muted-foreground mt-1.5">
            {feedback.verified_count > 0 && `확인 ${feedback.verified_count}회`}
            {feedback.verified_count > 0 && feedback.needs_update_count > 0 && ", "}
            {feedback.needs_update_count > 0 && `수정 요청 ${feedback.needs_update_count}회`}
            {feedback.last_verified_by && (
              <span className="ml-1">
                (마지막 확인: {feedback.last_verified_by}, {timeAgo(feedback.last_verified_at)})
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ---- Connections Tab ----
function ConnectionsTabContent({
  filePath,
  onCountChange,
}: {
  filePath: string;
  onCountChange: (total: number) => void;
}) {
  const [lineage, setLineage] = useState<LineageData | null>(null);
  const [backlinks, setBacklinks] = useState<BacklinkMap | null>(null);
  const [relatedDocs, setRelatedDocs] = useState<RelatedDoc[]>([]);
  const [relatedLoading, setRelatedLoading] = useState(false);
  const [showAllRelated, setShowAllRelated] = useState(false);
  const [showTimeline, setShowTimeline] = useState(false);
  const DEFAULT_VISIBLE = 3;
  const openTab = useWorkspaceStore((s) => s.openTab);
  const openGraphTab = useWorkspaceStore((s) => s.openGraphTab);

  const isLocal = typeof window !== "undefined" && window.location.hostname === "localhost";
  const base = isLocal ? "http://localhost:8001" : "";

  const [lineageVersion, setLineageVersion] = useState(0);

  // Listen for external lineage changes (e.g. undeprecate from ConflictDashboard)
  useEffect(() => {
    const handler = () => setLineageVersion((v) => v + 1);
    window.addEventListener("wiki:lineage-changed", handler);
    return () => window.removeEventListener("wiki:lineage-changed", handler);
  }, []);

  useEffect(() => {
    fetch(`/api/wiki/lineage/${encodeURIComponent(filePath)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then(setLineage)
      .catch(() => setLineage(null));

    fetch("/api/search/backlinks")
      .then((r) => (r.ok ? r.json() : null))
      .then(setBacklinks)
      .catch(() => setBacklinks(null));

    setRelatedLoading(true);
    if (!filePath.startsWith("_skills/") && !filePath.startsWith("_personas/")) {
      fetch(`${base}/api/search/related?path=${encodeURIComponent(filePath)}&limit=5`)
        .then((r) => (r.ok ? r.json() : []))
        .then((data: RelatedDoc[]) => setRelatedDocs(data))
        .catch(() => setRelatedDocs([]))
        .finally(() => setRelatedLoading(false));
    } else {
      setRelatedLoading(false);
    }
  }, [filePath, base, lineageVersion]);

  const forwardLinks = [...new Set(backlinks?.forward[filePath] ?? [])];
  const backwardLinks = [...new Set(backlinks?.backward[filePath] ?? [])];

  const totalConnections =
    (lineage?.supersedes ? 1 : 0) +
    (lineage?.superseded_by ? 1 : 0) +
    (lineage?.related?.length ?? 0) +
    forwardLinks.length +
    backwardLinks.length +
    relatedDocs.length;

  // Report count to parent
  useEffect(() => {
    onCountChange(totalConnections);
  }, [totalConnections, onCountChange]);

  return (
    <div className="space-y-2 text-xs">
      {/* Superseded by */}
      {lineage?.superseded_by && (
        <div className="flex items-center gap-1.5">
          <AlertTriangle className="h-3 w-3 text-amber-500 shrink-0" />
          <span className="text-amber-700 dark:text-amber-400">폐기됨 → 새 버전:</span>
          <button onClick={() => openTab(lineage.superseded_by!.path)} className="text-primary hover:underline font-medium truncate">
            {lineage.superseded_by.title || fileName(lineage.superseded_by.path)}
          </button>
        </div>
      )}

      {/* Supersedes */}
      {lineage?.supersedes && (
        <div className="flex items-center gap-1.5">
          <ArrowUp className="h-3 w-3 text-green-600 shrink-0" />
          <span className="text-muted-foreground">이전 버전:</span>
          <button onClick={() => openTab(lineage.supersedes!.path)} className="text-primary hover:underline truncate">
            {lineage.supersedes.title || fileName(lineage.supersedes.path)}
          </button>
          {lineage.supersedes.status === "deprecated" && (
            <span className="text-[10px] text-red-500">(deprecated)</span>
          )}
        </div>
      )}

      {/* Version history button */}
      {(lineage?.supersedes || lineage?.superseded_by) && !showTimeline && (
        <button
          onClick={() => setShowTimeline(true)}
          className="flex items-center gap-1.5 text-xs text-primary hover:text-primary/80 font-medium py-0.5"
        >
          <GitBranch className="h-3 w-3" />
          전체 버전 히스토리
        </button>
      )}

      {showTimeline && (
        <VersionTimeline filePath={filePath} onClose={() => setShowTimeline(false)} />
      )}

      {/* Related */}
      {lineage?.related && lineage.related.length > 0 && (
        <div className="flex items-center gap-1.5 flex-wrap">
          <Link2 className="h-3 w-3 text-blue-500 shrink-0" />
          <span className="text-muted-foreground">관련:</span>
          {lineage.related.map((r) => (
            <button key={r.path} onClick={() => openTab(r.path)} className="text-primary hover:underline truncate max-w-[150px]">
              {r.title || fileName(r.path)}
            </button>
          ))}
        </div>
      )}

      {/* Forward links */}
      {forwardLinks.length > 0 && (
        <div className="flex items-center gap-1.5 flex-wrap">
          <ArrowRight className="h-3 w-3 text-slate-400 shrink-0" />
          <span className="text-muted-foreground">참조:</span>
          {forwardLinks.map((path) => (
            <button key={path} onClick={() => openTab(path)} className="text-primary hover:underline truncate max-w-[150px]">
              {fileName(path)}
            </button>
          ))}
        </div>
      )}

      {/* Backward links */}
      {backwardLinks.length > 0 && (
        <div className="flex items-center gap-1.5 flex-wrap">
          <ArrowLeft className="h-3 w-3 text-slate-400 shrink-0" />
          <span className="text-muted-foreground">역참조:</span>
          {backwardLinks.map((path) => (
            <button key={path} onClick={() => openTab(path)} className="text-primary hover:underline truncate max-w-[150px]">
              {fileName(path)}
            </button>
          ))}
        </div>
      )}

      {/* AI-recommended */}
      {(relatedDocs.length > 0 || relatedLoading) && (
        <div className="border-t border-dashed pt-2 mt-1">
          <div className="flex items-center gap-1.5 mb-1">
            <Sparkles className="h-3 w-3 text-purple-500 shrink-0" />
            <span className="text-muted-foreground font-medium">참고할 만한 문서</span>
            {relatedLoading && <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />}
          </div>
          {(showAllRelated ? relatedDocs : relatedDocs.slice(0, DEFAULT_VISIBLE)).map((r) => (
            <div key={r.path} className="flex items-center gap-1.5 pl-4 py-0.5">
              <span
                className={`inline-block h-1.5 w-1.5 rounded-full shrink-0 ${
                  r.confidence_tier === "high" ? "bg-green-500"
                    : r.confidence_tier === "medium" ? "bg-yellow-500" : "bg-gray-400"
                }`}
                title={`신뢰도 ${r.confidence_score >= 0 ? r.confidence_score : "?"}`}
              />
              <button onClick={() => openTab(r.path)} className="text-primary hover:underline truncate max-w-[180px]" title={r.snippet || r.title}>
                {r.title || fileName(r.path)}
              </button>
              <span className="text-[10px] text-muted-foreground shrink-0">
                {Math.round(r.similarity * 100)}%
              </span>
            </div>
          ))}
          {relatedDocs.length > DEFAULT_VISIBLE && (
            <button
              onClick={() => setShowAllRelated((v) => !v)}
              className="text-[10px] text-muted-foreground hover:text-primary pl-4 mt-0.5"
            >
              {showAllRelated ? "접기" : `더 보기 (+${relatedDocs.length - DEFAULT_VISIBLE})`}
            </button>
          )}
        </div>
      )}

      {/* Graph link */}
      <div className="pt-1">
        <button
          onClick={() => openGraphTab(filePath)}
          className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-primary transition-colors"
        >
          <Network className="h-3 w-3" />
          그래프에서 보기
        </button>
      </div>

      {totalConnections === 0 && !relatedLoading && (
        <div className="text-muted-foreground py-2">연결된 문서가 없습니다.</div>
      )}
    </div>
  );
}
