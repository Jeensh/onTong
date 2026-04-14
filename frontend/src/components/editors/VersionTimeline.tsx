"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { useWorkspaceStore } from "@/lib/workspace/useWorkspaceStore";
import { GitBranch, X } from "lucide-react";

interface ChainNode {
  path: string;
  title: string;
  status: string;
  created: string;
  updated: string;
  created_by: string;
}

interface BranchInfo {
  path: string;
  title: string;
  status: string;
}

interface VersionChainData {
  chain: ChainNode[];
  current_index: number;
  branches: BranchInfo[];
}

const STATUS_COLORS: Record<string, string> = {
  approved: "border-green-500 text-green-600",
  deprecated: "border-red-400 text-red-500",
  draft: "border-gray-400 text-gray-500",
};

export function VersionTimeline({
  filePath,
  onClose,
}: {
  filePath: string;
  onClose: () => void;
}) {
  const [data, setData] = useState<VersionChainData | null>(null);
  const [loading, setLoading] = useState(true);
  const [version, setVersion] = useState(0);
  const openTab = useWorkspaceStore((s) => s.openTab);

  useEffect(() => {
    const handler = () => setVersion((v) => v + 1);
    window.addEventListener("wiki:lineage-changed", handler);
    return () => window.removeEventListener("wiki:lineage-changed", handler);
  }, []);

  useEffect(() => {
    setLoading(true);
    fetch(`/api/wiki/version-chain/${encodeURIComponent(filePath)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch(() => {
        setData(null);
        setLoading(false);
      });
  }, [filePath, version]);

  if (loading) {
    return (
      <div className="p-4 text-sm text-muted-foreground">
        버전 히스토리 로딩 중...
      </div>
    );
  }

  if (!data || data.chain.length <= 1) {
    return (
      <div className="p-4 text-sm text-muted-foreground">
        버전 체인이 없습니다. (단일 문서)
        <button onClick={onClose} className="ml-2 text-primary hover:underline text-xs">
          닫기
        </button>
      </div>
    );
  }

  return (
    <div className="border rounded-lg bg-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium flex items-center gap-1.5">
          <GitBranch className="h-4 w-4" />
          버전 히스토리 ({data.chain.length}개)
        </h3>
        <button
          onClick={onClose}
          className="text-muted-foreground hover:text-foreground"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Timeline */}
      <div className="relative pl-4">
        {/* Vertical line */}
        <div className="absolute left-[7px] top-2 bottom-2 w-px bg-border" />

        {data.chain.map((node, i) => {
          const isCurrent = i === data.current_index;
          return (
            <div key={node.path} className="relative flex items-start gap-3 pb-3">
              {/* Dot */}
              <div
                className={`relative z-10 mt-1.5 h-3 w-3 rounded-full border-2 ${
                  isCurrent
                    ? "bg-primary border-primary"
                    : node.status === "deprecated"
                    ? "bg-red-400 border-red-400"
                    : node.status === "approved"
                    ? "bg-green-500 border-green-500"
                    : "bg-muted border-border"
                }`}
              />

              {/* Content */}
              <div className={`flex-1 min-w-0 ${isCurrent ? "bg-accent/50 rounded px-2 py-1 -mx-1" : ""}`}>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      openTab(node.path);
                      onClose();
                    }}
                    className={`text-sm truncate hover:underline ${
                      isCurrent ? "font-semibold text-foreground" : "text-primary"
                    }`}
                  >
                    {node.title || node.path.split("/").pop()?.replace(".md", "")}
                  </button>
                  {node.status && (
                    <Badge
                      variant="outline"
                      className={`text-[10px] px-1 py-0 ${STATUS_COLORS[node.status] || ""}`}
                    >
                      {node.status}
                    </Badge>
                  )}
                  {isCurrent && (
                    <span className="text-[10px] text-muted-foreground">(현재)</span>
                  )}
                </div>
                <div className="text-[11px] text-muted-foreground mt-0.5">
                  {node.updated && <span>{node.updated.slice(0, 10)}</span>}
                  {node.created_by && <span className="ml-2">by {node.created_by}</span>}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Branches */}
      {data.branches.length > 0 && (
        <div className="border-t pt-2">
          <div className="text-[11px] text-amber-600 font-medium mb-1">
            분기 감지: 같은 문서를 대체하는 다른 버전
          </div>
          {data.branches.map((b) => (
            <button
              key={b.path}
              onClick={() => {
                openTab(b.path);
                onClose();
              }}
              className="text-xs text-primary hover:underline block"
            >
              {b.title || b.path.split("/").pop()?.replace(".md", "")}
              {b.status && (
                <Badge
                  variant="outline"
                  className={`ml-1 text-[9px] px-1 py-0 ${STATUS_COLORS[b.status] || ""}`}
                >
                  {b.status}
                </Badge>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
