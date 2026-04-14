"use client";

import { useEffect, useState } from "react";
import { ArrowUp, ArrowDown, Link2, AlertTriangle, History } from "lucide-react";
import { useWorkspaceStore } from "@/lib/workspace/useWorkspaceStore";
import { VersionTimeline } from "./VersionTimeline";

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

export function LineageWidget({ filePath }: { filePath: string }) {
  const [lineage, setLineage] = useState<LineageData | null>(null);
  const [showTimeline, setShowTimeline] = useState(false);
  const [version, setVersion] = useState(0);
  const openTab = useWorkspaceStore((s) => s.openTab);

  useEffect(() => {
    const handler = () => setVersion((v) => v + 1);
    window.addEventListener("wiki:lineage-changed", handler);
    return () => window.removeEventListener("wiki:lineage-changed", handler);
  }, []);

  useEffect(() => {
    fetch(`/api/wiki/lineage/${encodeURIComponent(filePath)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then(setLineage)
      .catch(() => setLineage(null));
    setShowTimeline(false);
  }, [filePath, version]);

  if (!lineage) return null;

  const hasLineage =
    lineage.supersedes || lineage.superseded_by || lineage.related.length > 0;

  if (!hasLineage) return null;

  return (
    <div className="border-b bg-muted/10 px-4 py-2 space-y-1.5">
      {/* Superseded by (this doc is old) — full-width banner */}
      {lineage.superseded_by && (
        <div className="flex items-center gap-1.5 text-xs bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded px-2 py-1.5 -mx-1">
          <AlertTriangle className="h-3.5 w-3.5 text-amber-500 flex-shrink-0" />
          <span className="text-amber-700 dark:text-amber-400">
            이 문서는 폐기되었습니다. 새 버전:
          </span>
          <button
            onClick={() => openTab(lineage.superseded_by!.path)}
            className="text-primary hover:underline font-medium"
          >
            {lineage.superseded_by.title || lineage.superseded_by.path.split("/").pop()}
          </button>
        </div>
      )}

      {/* Supersedes (this doc is newer) */}
      {lineage.supersedes && (
        <div className="flex items-center gap-1.5 text-xs">
          <ArrowUp className="h-3 w-3 text-green-600 flex-shrink-0" />
          <span className="text-muted-foreground">이전 버전:</span>
          <button
            onClick={() => openTab(lineage.supersedes!.path)}
            className="text-primary hover:underline"
          >
            {lineage.supersedes.title || lineage.supersedes.path.split("/").pop()}
          </button>
          {lineage.supersedes.status === "deprecated" && (
            <span className="text-[10px] text-red-500">(deprecated)</span>
          )}
        </div>
      )}

      {/* Related */}
      {lineage.related.length > 0 && (
        <div className="flex items-center gap-1.5 text-xs flex-wrap">
          <Link2 className="h-3 w-3 text-muted-foreground flex-shrink-0" />
          <span className="text-muted-foreground">관련 문서:</span>
          {lineage.related.map((r) => (
            <button
              key={r.path}
              onClick={() => openTab(r.path)}
              className="text-primary hover:underline"
            >
              {r.title || r.path.split("/").pop()}
              {r.status === "deprecated" && (
                <span className="text-[9px] text-red-500 ml-0.5">(deprecated)</span>
              )}
            </button>
          ))}
        </div>
      )}

      {/* Version history button */}
      {(lineage.supersedes || lineage.superseded_by) && (
        <button
          onClick={() => setShowTimeline(!showTimeline)}
          className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
        >
          <History className="h-3 w-3" />
          {showTimeline ? "타임라인 닫기" : "전체 버전 히스토리"}
        </button>
      )}

      {showTimeline && (
        <VersionTimeline
          filePath={filePath}
          onClose={() => setShowTimeline(false)}
        />
      )}
    </div>
  );
}
