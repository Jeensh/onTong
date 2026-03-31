"use client";

import { useEffect, useState } from "react";
import { ArrowUp, ArrowDown, Link2, AlertTriangle } from "lucide-react";
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

export function LineageWidget({ filePath }: { filePath: string }) {
  const [lineage, setLineage] = useState<LineageData | null>(null);
  const openTab = useWorkspaceStore((s) => s.openTab);

  useEffect(() => {
    fetch(`/api/wiki/lineage/${encodeURIComponent(filePath)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then(setLineage)
      .catch(() => setLineage(null));
  }, [filePath]);

  if (!lineage) return null;

  const hasLineage =
    lineage.supersedes || lineage.superseded_by || lineage.related.length > 0;

  if (!hasLineage) return null;

  return (
    <div className="border-b bg-muted/10 px-4 py-2 space-y-1.5">
      {/* Superseded by (this doc is old) */}
      {lineage.superseded_by && (
        <div className="flex items-center gap-1.5 text-xs">
          <AlertTriangle className="h-3 w-3 text-amber-500 flex-shrink-0" />
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
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
