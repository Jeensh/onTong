"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import { FileText, Loader2, ArrowRight, Check } from "lucide-react";
import { toast } from "sonner";
import { useWorkspaceStore } from "@/lib/workspace/useWorkspaceStore";

interface CompareFile {
  path: string;
  title: string;
  content: string;
  metadata: Record<string, string>;
}

interface DiffLine {
  type: "same" | "added" | "removed" | "changed";
  lineA?: string;
  lineB?: string;
  lineNum: number;
}

function computeDiff(textA: string, textB: string): DiffLine[] {
  const linesA = textA.split("\n");
  const linesB = textB.split("\n");
  const result: DiffLine[] = [];
  const maxLen = Math.max(linesA.length, linesB.length);

  for (let i = 0; i < maxLen; i++) {
    const a = i < linesA.length ? linesA[i] : undefined;
    const b = i < linesB.length ? linesB[i] : undefined;

    if (a === b) {
      result.push({ type: "same", lineA: a, lineB: b, lineNum: i + 1 });
    } else if (a !== undefined && b !== undefined) {
      result.push({ type: "changed", lineA: a, lineB: b, lineNum: i + 1 });
    } else if (a === undefined) {
      result.push({ type: "added", lineB: b, lineNum: i + 1 });
    } else {
      result.push({ type: "removed", lineA: a, lineNum: i + 1 });
    }
  }
  return result;
}

export function DiffViewer({ pathA, pathB }: { pathA: string; pathB: string }) {
  const [fileA, setFileA] = useState<CompareFile | null>(null);
  const [fileB, setFileB] = useState<CompareFile | null>(null);
  const [loading, setLoading] = useState(true);
  const [deprecating, setDeprecating] = useState<string | null>(null);
  const addResolvedConflict = useWorkspaceStore((s) => s.addResolvedConflict);

  useEffect(() => {
    setLoading(true);
    fetch(`/api/wiki/compare?path_a=${encodeURIComponent(pathA)}&path_b=${encodeURIComponent(pathB)}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => {
        setFileA(data.file_a);
        setFileB(data.file_b);
      })
      .catch((e) => toast.error("문서 비교 실패: " + (e as Error).message))
      .finally(() => setLoading(false));
  }, [pathA, pathB]);

  const handleMarkLatest = useCallback(async (latestPath: string, deprecatePath: string) => {
    setDeprecating(deprecatePath);
    try {
      const res = await fetch(
        `/api/conflict/deprecate?path=${encodeURIComponent(deprecatePath)}&superseded_by=${encodeURIComponent(latestPath)}`,
        { method: "POST" },
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      toast.success(`${deprecatePath.split("/").pop()} → deprecated`);
      // Mark conflict pair as resolved in workspace store
      const pairKey = `${pathA}__${pathB}`;
      addResolvedConflict(pairKey);
      // Refresh
      const r = await fetch(`/api/wiki/compare?path_a=${encodeURIComponent(pathA)}&path_b=${encodeURIComponent(pathB)}`);
      const data = await r.json();
      setFileA(data.file_a);
      setFileB(data.file_b);
    } catch (e) {
      toast.error("변경 실패: " + (e as Error).message);
    } finally {
      setDeprecating(null);
    }
  }, [pathA, pathB]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin mr-2" />
        문서 비교 로딩 중...
      </div>
    );
  }

  if (!fileA || !fileB) {
    return <div className="p-6 text-sm text-muted-foreground">문서를 불러올 수 없습니다.</div>;
  }

  const diff = computeDiff(fileA.content, fileB.content);
  const changedCount = diff.filter((d) => d.type !== "same").length;

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="border-b px-4 py-3 flex items-center justify-between bg-muted/20">
        <div className="flex items-center gap-4 text-sm">
          <MetaBadge file={fileA} label="A" />
          <ArrowRight className="h-4 w-4 text-muted-foreground" />
          <MetaBadge file={fileB} label="B" />
        </div>
        <span className="text-xs text-muted-foreground">
          {changedCount}줄 차이
        </span>
      </div>

      {/* Action buttons */}
      <div className="border-b px-4 py-2 flex items-center gap-2">
        <button
          onClick={() => handleMarkLatest(pathA, pathB)}
          disabled={deprecating !== null || fileB.metadata.status === "deprecated"}
          className="inline-flex items-center gap-1 rounded-md border border-green-300 px-2.5 py-1 text-xs text-green-700 hover:bg-green-50 dark:border-green-700 dark:text-green-400 dark:hover:bg-green-950/30 disabled:opacity-50"
        >
          <Check className="h-3 w-3" />
          A가 최신 (B를 deprecated)
        </button>
        <button
          onClick={() => handleMarkLatest(pathB, pathA)}
          disabled={deprecating !== null || fileA.metadata.status === "deprecated"}
          className="inline-flex items-center gap-1 rounded-md border border-green-300 px-2.5 py-1 text-xs text-green-700 hover:bg-green-50 dark:border-green-700 dark:text-green-400 dark:hover:bg-green-950/30 disabled:opacity-50"
        >
          <Check className="h-3 w-3" />
          B가 최신 (A를 deprecated)
        </button>
      </div>

      {/* Diff content */}
      <div className="flex-1 overflow-auto">
        <div className="grid grid-cols-2 divide-x text-xs font-mono">
          {/* Column headers */}
          <div className="sticky top-0 bg-muted/80 px-3 py-1.5 text-muted-foreground font-sans font-medium border-b">
            {fileA.path.split("/").pop()}
            {fileA.metadata.status === "deprecated" && (
              <span className="ml-1 text-red-500">(deprecated)</span>
            )}
          </div>
          <div className="sticky top-0 bg-muted/80 px-3 py-1.5 text-muted-foreground font-sans font-medium border-b">
            {fileB.path.split("/").pop()}
            {fileB.metadata.status === "deprecated" && (
              <span className="ml-1 text-red-500">(deprecated)</span>
            )}
          </div>

          {/* Diff lines */}
          {diff.map((line, idx) => (
            <Fragment key={idx}>
              <div
                className={`px-3 py-0.5 whitespace-pre-wrap break-all ${
                  line.type === "removed"
                    ? "bg-red-100 dark:bg-red-950/40 text-red-800 dark:text-red-300"
                    : line.type === "changed"
                    ? "bg-amber-50 dark:bg-amber-950/30 text-amber-900 dark:text-amber-200"
                    : ""
                }`}
              >
                <span className="inline-block w-6 text-right mr-2 text-muted-foreground/50 select-none">
                  {line.lineA !== undefined ? line.lineNum : ""}
                </span>
                {line.lineA ?? ""}
              </div>
              <div
                className={`px-3 py-0.5 whitespace-pre-wrap break-all ${
                  line.type === "added"
                    ? "bg-green-100 dark:bg-green-950/40 text-green-800 dark:text-green-300"
                    : line.type === "changed"
                    ? "bg-amber-50 dark:bg-amber-950/30 text-amber-900 dark:text-amber-200"
                    : ""
                }`}
              >
                <span className="inline-block w-6 text-right mr-2 text-muted-foreground/50 select-none">
                  {line.lineB !== undefined ? line.lineNum : ""}
                </span>
                {line.lineB ?? ""}
              </div>
            </Fragment>
          ))}
        </div>
      </div>
    </div>
  );
}

function MetaBadge({ file, label }: { file: CompareFile; label: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="inline-flex items-center justify-center h-5 w-5 rounded bg-primary/10 text-primary text-[10px] font-bold">
        {label}
      </span>
      <FileText className="h-3.5 w-3.5 text-muted-foreground" />
      <span className="font-medium">{file.path.split("/").pop()}</span>
      {file.metadata.status && (
        <span className={`text-[10px] px-1 rounded ${
          file.metadata.status === "approved" ? "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400" :
          file.metadata.status === "deprecated" ? "bg-red-100 text-red-600 dark:bg-red-900/40 dark:text-red-400" :
          "bg-gray-100 text-gray-600"
        }`}>
          {file.metadata.status}
        </span>
      )}
      {file.metadata.updated && (
        <span className="text-[10px] text-muted-foreground">{file.metadata.updated}</span>
      )}
    </div>
  );
}
