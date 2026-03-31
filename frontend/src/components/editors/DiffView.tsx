"use client";

import { useCallback, useMemo, useState } from "react";
import { Check, Undo2, Pencil, CheckSquare, Square } from "lucide-react";

export type DiffAction = "accept" | "revert" | "edit";

interface DiffViewProps {
  oldContent: string;
  newContent: string;
  filePath: string;
  onAction: (action: DiffAction, partialContent?: string) => void;
}

type DiffLineType = "same" | "add" | "del";

interface DiffLine {
  type: DiffLineType;
  text: string;
  oldNum?: number;
  newNum?: number;
  hunkIdx: number; // which hunk this line belongs to (-1 for "same")
}

interface Hunk {
  idx: number;
  startLine: number; // index in the diff lines array
  endLine: number;
  addCount: number;
  delCount: number;
}

function computeDiff(oldText: string, newText: string): { lines: DiffLine[]; hunks: Hunk[] } {
  const oldLines = oldText.split("\n");
  const newLines = newText.split("\n");
  const m = oldLines.length;
  const n = newLines.length;

  // LCS table
  const dp: number[][] = Array.from({ length: m + 1 }, () =>
    Array(n + 1).fill(0)
  );
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      dp[i][j] =
        oldLines[i - 1] === newLines[j - 1]
          ? dp[i - 1][j - 1] + 1
          : Math.max(dp[i - 1][j], dp[i][j - 1]);
    }
  }

  // Backtrack to build raw diff
  const raw: Omit<DiffLine, "hunkIdx">[] = [];
  let i = m;
  let j = n;
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && oldLines[i - 1] === newLines[j - 1]) {
      raw.push({ type: "same", text: oldLines[i - 1], oldNum: i, newNum: j });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      raw.push({ type: "add", text: newLines[j - 1], newNum: j });
      j--;
    } else {
      raw.push({ type: "del", text: oldLines[i - 1], oldNum: i });
      i--;
    }
  }
  raw.reverse();

  // Group consecutive add/del lines into hunks
  const hunks: Hunk[] = [];
  const lines: DiffLine[] = [];
  let currentHunk = -1;

  for (let k = 0; k < raw.length; k++) {
    const line = raw[k];
    if (line.type !== "same") {
      // Start a new hunk if previous line was "same" or this is the first line
      if (k === 0 || raw[k - 1].type === "same") {
        currentHunk++;
        hunks.push({ idx: currentHunk, startLine: k, endLine: k, addCount: 0, delCount: 0 });
      }
      hunks[hunks.length - 1].endLine = k;
      if (line.type === "add") hunks[hunks.length - 1].addCount++;
      else hunks[hunks.length - 1].delCount++;
      lines.push({ ...line, hunkIdx: currentHunk });
    } else {
      lines.push({ ...line, hunkIdx: -1 });
    }
  }

  return { lines, hunks };
}

function buildPartialContent(
  lines: DiffLine[],
  hunks: Hunk[],
  accepted: Set<number>,
  oldContent: string
): string {
  // Reconstruct content: for accepted hunks keep new lines, for rejected hunks keep old lines
  const result: string[] = [];

  for (const line of lines) {
    if (line.type === "same") {
      result.push(line.text);
    } else if (accepted.has(line.hunkIdx)) {
      // Hunk accepted: keep adds, skip dels
      if (line.type === "add") result.push(line.text);
      // del lines are removed (skipped)
    } else {
      // Hunk rejected: keep dels, skip adds
      if (line.type === "del") result.push(line.text);
      // add lines are removed (skipped)
    }
  }

  return result.join("\n");
}

export function DiffView({ oldContent, newContent, filePath, onAction }: DiffViewProps) {
  const { lines, hunks } = useMemo(
    () => computeDiff(oldContent, newContent),
    [oldContent, newContent]
  );

  // All hunks accepted by default
  const [accepted, setAccepted] = useState<Set<number>>(
    () => new Set(hunks.map((h) => h.idx))
  );

  const allAccepted = accepted.size === hunks.length;
  const noneAccepted = accepted.size === 0;

  const toggleHunk = useCallback((idx: number) => {
    setAccepted((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  }, []);

  const toggleAll = useCallback(() => {
    if (allAccepted) {
      setAccepted(new Set());
    } else {
      setAccepted(new Set(hunks.map((h) => h.idx)));
    }
  }, [allAccepted, hunks]);

  const handleApply = useCallback(() => {
    if (allAccepted) {
      onAction("accept");
    } else if (noneAccepted) {
      onAction("revert");
    } else {
      const partial = buildPartialContent(lines, hunks, accepted, oldContent);
      onAction("accept", partial);
    }
  }, [allAccepted, noneAccepted, lines, hunks, accepted, oldContent, onAction]);

  const totalAdd = hunks.reduce((s, h) => s + h.addCount, 0);
  const totalDel = hunks.reduce((s, h) => s + h.delCount, 0);
  const acceptedAdd = hunks.filter((h) => accepted.has(h.idx)).reduce((s, h) => s + h.addCount, 0);
  const acceptedDel = hunks.filter((h) => accepted.has(h.idx)).reduce((s, h) => s + h.delCount, 0);

  // Build a set of hunk start lines for rendering hunk toggle buttons
  const hunkStartLines = new Map<number, Hunk>();
  for (const line of lines) {
    if (line.hunkIdx >= 0 && !hunkStartLines.has(line.hunkIdx)) {
      hunkStartLines.set(line.hunkIdx, hunks[line.hunkIdx]);
    }
  }
  // Track first occurrence of each hunk in rendered order
  const seenHunks = new Set<number>();

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b bg-muted/50">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium">AI 문서 수정 변경사항</span>
          <span className="text-xs text-muted-foreground truncate max-w-40">{filePath}</span>
          <span className="text-xs text-green-600 font-mono">+{totalAdd}</span>
          <span className="text-xs text-red-600 font-mono">-{totalDel}</span>
          {!allAccepted && !noneAccepted && (
            <span className="text-xs text-muted-foreground">
              (적용: +{acceptedAdd} -{acceptedDel})
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Toggle all */}
          <button
            onClick={toggleAll}
            className="flex items-center gap-1 px-2 py-1 text-xs rounded-md border hover:bg-muted transition-colors"
            title={allAccepted ? "전체 해제" : "전체 선택"}
          >
            {allAccepted ? <CheckSquare size={12} /> : <Square size={12} />}
            전체
          </button>
          {/* Revert */}
          <button
            onClick={() => onAction("revert")}
            className="flex items-center gap-1.5 px-3 py-1 text-xs rounded-md border border-destructive/50 text-destructive hover:bg-destructive/10 transition-colors"
          >
            <Undo2 size={12} />
            되돌리기
          </button>
          {/* Edit manually */}
          <button
            onClick={() => onAction("edit")}
            className="flex items-center gap-1.5 px-3 py-1 text-xs rounded-md border hover:bg-muted transition-colors"
          >
            <Pencil size={12} />
            직접 편집
          </button>
          {/* Apply */}
          <button
            onClick={handleApply}
            className="flex items-center gap-1.5 px-3 py-1 text-xs rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            <Check size={12} />
            {noneAccepted ? "변경 없이 닫기" : allAccepted ? "전체 적용" : "선택 적용"}
          </button>
        </div>
      </div>

      {/* Diff body */}
      <div className="flex-1 overflow-auto font-mono text-sm">
        {lines.map((line, idx) => {
          const isFirstInHunk = line.hunkIdx >= 0 && !seenHunks.has(line.hunkIdx);
          if (isFirstInHunk) seenHunks.add(line.hunkIdx);
          const isAccepted = line.hunkIdx >= 0 && accepted.has(line.hunkIdx);
          const isRejected = line.hunkIdx >= 0 && !accepted.has(line.hunkIdx);

          return (
            <div
              key={idx}
              className={`flex ${
                isRejected
                  ? "opacity-35"
                  : line.type === "add"
                  ? "bg-green-50 dark:bg-green-950/30"
                  : line.type === "del"
                  ? "bg-red-50 dark:bg-red-950/30"
                  : ""
              }`}
            >
              {/* Hunk checkbox column */}
              <span className="w-7 shrink-0 flex items-center justify-center border-r">
                {isFirstInHunk && (
                  <button
                    onClick={() => toggleHunk(line.hunkIdx)}
                    className="hover:text-primary transition-colors"
                    title={isAccepted ? "이 변경 제외" : "이 변경 포함"}
                  >
                    {isAccepted ? (
                      <CheckSquare size={13} className="text-primary" />
                    ) : (
                      <Square size={13} className="text-muted-foreground" />
                    )}
                  </button>
                )}
              </span>
              {/* Old line number */}
              <span className="w-9 shrink-0 text-right pr-2 text-xs text-muted-foreground select-none border-r leading-6">
                {line.type !== "add" ? line.oldNum : ""}
              </span>
              {/* New line number */}
              <span className="w-9 shrink-0 text-right pr-2 text-xs text-muted-foreground select-none border-r leading-6">
                {line.type !== "del" ? line.newNum : ""}
              </span>
              {/* Indicator */}
              <span
                className={`w-6 shrink-0 text-center select-none leading-6 ${
                  line.type === "add"
                    ? "text-green-600"
                    : line.type === "del"
                    ? "text-red-600"
                    : "text-muted-foreground"
                }`}
              >
                {line.type === "add" ? "+" : line.type === "del" ? "-" : " "}
              </span>
              {/* Content */}
              <span
                className={`flex-1 px-2 whitespace-pre-wrap break-all leading-6 ${
                  line.type === "add"
                    ? "text-green-800 dark:text-green-300"
                    : line.type === "del"
                    ? "text-red-800 dark:text-red-300 line-through"
                    : ""
                }`}
              >
                {line.text || "\u00A0"}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
