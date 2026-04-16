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

  // Only show the deprecation banner inline (other lineage data is in the drawer)
  if (!lineage.superseded_by) return null;

  return (
    <div className="border-b bg-muted/10 px-4 py-2">
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
    </div>
  );
}
