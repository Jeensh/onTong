"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ArrowUp,
  ArrowDown,
  Link2,
  ArrowRight,
  ArrowLeft,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  Network,
  Sparkles,
  Loader2,
} from "lucide-react";
import { useWorkspaceStore } from "@/lib/workspace/useWorkspaceStore";

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

function fileName(path: string): string {
  return path.split("/").pop()?.replace(".md", "") ?? path;
}

export function LinkedDocsPanel({ filePath }: { filePath: string }) {
  const [lineage, setLineage] = useState<LineageData | null>(null);
  const [backlinks, setBacklinks] = useState<BacklinkMap | null>(null);
  const [relatedDocs, setRelatedDocs] = useState<RelatedDoc[]>([]);
  const [showAllRelated, setShowAllRelated] = useState(false);
  const DEFAULT_VISIBLE = 2;
  const [relatedLoading, setRelatedLoading] = useState(false);
  const [expanded, setExpanded] = useState(true);
  const openTab = useWorkspaceStore((s) => s.openTab);
  const openGraphTab = useWorkspaceStore((s) => s.openGraphTab);

  const isLocal = typeof window !== "undefined" && window.location.hostname === "localhost";
  const base = isLocal ? "http://localhost:8001" : "";

  const fetchRelated = useCallback(() => {
    if (!filePath || filePath.startsWith("_skills/") || filePath.startsWith("_personas/")) return;
    setRelatedLoading(true);
    fetch(`${base}/api/search/related?path=${encodeURIComponent(filePath)}&limit=5`)
      .then((r) => (r.ok ? r.json() : []))
      .then((data: RelatedDoc[]) => setRelatedDocs(data))
      .catch(() => setRelatedDocs([]))
      .finally(() => setRelatedLoading(false));
  }, [filePath, base]);

  useEffect(() => {
    fetch(`/api/wiki/lineage/${encodeURIComponent(filePath)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then(setLineage)
      .catch(() => setLineage(null));

    fetch("/api/search/backlinks")
      .then((r) => (r.ok ? r.json() : null))
      .then(setBacklinks)
      .catch(() => setBacklinks(null));

    // Fetch AI-recommended related docs (debounced via useCallback)
    const timer = setTimeout(fetchRelated, 500);
    return () => clearTimeout(timer);
  }, [filePath, fetchRelated]);

  const forwardLinks = [...new Set(backlinks?.forward[filePath] ?? [])];
  const backwardLinks = [...new Set(backlinks?.backward[filePath] ?? [])];
  const hasLineage = lineage?.supersedes || lineage?.superseded_by || (lineage?.related?.length ?? 0) > 0;
  const hasLinks = forwardLinks.length > 0 || backwardLinks.length > 0;
  const hasRelated = relatedDocs.length > 0;

  if (!hasLineage && !hasLinks && !hasRelated && !relatedLoading) return null;

  const totalConnections =
    (lineage?.supersedes ? 1 : 0) +
    (lineage?.superseded_by ? 1 : 0) +
    (lineage?.related?.length ?? 0) +
    forwardLinks.length +
    backwardLinks.length +
    relatedDocs.length;

  return (
    <div className="border-b bg-muted/10">
      {/* Header - always visible */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-1.5 w-full px-4 py-1.5 text-xs text-muted-foreground hover:bg-muted/20 transition-colors"
      >
        {expanded ? (
          <ChevronDown className="h-3 w-3" />
        ) : (
          <ChevronRight className="h-3 w-3" />
        )}
        <Network className="h-3 w-3" />
        <span>연결된 문서</span>
        <span className="bg-muted rounded-full px-1.5 py-0 text-[10px] ml-0.5">
          {totalConnections}
        </span>
        {!expanded && (
          <span
            role="link"
            tabIndex={0}
            onClick={(e) => {
              e.stopPropagation();
              openGraphTab(filePath);
            }}
            className="ml-auto text-[10px] text-primary hover:underline cursor-pointer"
          >
            그래프 보기
          </span>
        )}
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="px-4 pb-2 space-y-1.5">
          {/* Superseded by (this doc is old) */}
          {lineage?.superseded_by && (
            <div className="flex items-center gap-1.5 text-xs">
              <AlertTriangle className="h-3 w-3 text-amber-500 shrink-0" />
              <span className="text-amber-700 dark:text-amber-400">폐기됨 → 새 버전:</span>
              <button
                onClick={() => openTab(lineage.superseded_by!.path)}
                className="text-primary hover:underline font-medium truncate"
              >
                {lineage.superseded_by.title || fileName(lineage.superseded_by.path)}
              </button>
            </div>
          )}

          {/* Supersedes (this doc is newer) */}
          {lineage?.supersedes && (
            <div className="flex items-center gap-1.5 text-xs">
              <ArrowUp className="h-3 w-3 text-green-600 shrink-0" />
              <span className="text-muted-foreground">이전 버전:</span>
              <button
                onClick={() => openTab(lineage.supersedes!.path)}
                className="text-primary hover:underline truncate"
              >
                {lineage.supersedes.title || fileName(lineage.supersedes.path)}
              </button>
              {lineage.supersedes.status === "deprecated" && (
                <span className="text-[10px] text-red-500">(deprecated)</span>
              )}
            </div>
          )}

          {/* Related */}
          {lineage?.related && lineage.related.length > 0 && (
            <div className="flex items-center gap-1.5 text-xs flex-wrap">
              <Link2 className="h-3 w-3 text-blue-500 shrink-0" />
              <span className="text-muted-foreground">관련:</span>
              {lineage.related.map((r) => (
                <button
                  key={r.path}
                  onClick={() => openTab(r.path)}
                  className="text-primary hover:underline truncate max-w-[150px]"
                >
                  {r.title || fileName(r.path)}
                </button>
              ))}
            </div>
          )}

          {/* Forward links (this doc links to) */}
          {forwardLinks.length > 0 && (
            <div className="flex items-center gap-1.5 text-xs flex-wrap">
              <ArrowRight className="h-3 w-3 text-slate-400 shrink-0" />
              <span className="text-muted-foreground">참조:</span>
              {forwardLinks.map((path) => (
                <button
                  key={path}
                  onClick={() => openTab(path)}
                  className="text-primary hover:underline truncate max-w-[150px]"
                >
                  {fileName(path)}
                </button>
              ))}
            </div>
          )}

          {/* Backward links (linked from) */}
          {backwardLinks.length > 0 && (
            <div className="flex items-center gap-1.5 text-xs flex-wrap">
              <ArrowLeft className="h-3 w-3 text-slate-400 shrink-0" />
              <span className="text-muted-foreground">역참조:</span>
              {backwardLinks.map((path) => (
                <button
                  key={path}
                  onClick={() => openTab(path)}
                  className="text-primary hover:underline truncate max-w-[150px]"
                >
                  {fileName(path)}
                </button>
              ))}
            </div>
          )}

          {/* AI-recommended related documents */}
          {(relatedDocs.length > 0 || relatedLoading) && (
            <div className="border-t border-dashed pt-1.5 mt-1">
              <div className="flex items-center gap-1.5 text-xs mb-1">
                <Sparkles className="h-3 w-3 text-purple-500 shrink-0" />
                <span className="text-muted-foreground font-medium">참고할 만한 문서</span>
                {relatedLoading && <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />}
              </div>
              {(showAllRelated ? relatedDocs : relatedDocs.slice(0, DEFAULT_VISIBLE)).map((r) => (
                <div key={r.path} className="flex items-center gap-1.5 text-xs pl-4 py-0.5">
                  <span
                    className={`inline-block h-1.5 w-1.5 rounded-full shrink-0 ${
                      r.confidence_tier === "high"
                        ? "bg-green-500"
                        : r.confidence_tier === "medium"
                        ? "bg-yellow-500"
                        : "bg-gray-400"
                    }`}
                    title={`신뢰도 ${r.confidence_score >= 0 ? r.confidence_score : "?"}`}
                  />
                  <button
                    onClick={() => openTab(r.path)}
                    className="text-primary hover:underline truncate max-w-[180px]"
                    title={r.snippet || r.title}
                  >
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
          <div className="pt-0.5">
            <button
              onClick={() => openGraphTab(filePath)}
              className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-primary transition-colors"
            >
              <Network className="h-3 w-3" />
              그래프에서 보기
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
