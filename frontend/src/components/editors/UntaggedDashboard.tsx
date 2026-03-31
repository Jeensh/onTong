"use client";

import { useCallback, useEffect, useState } from "react";
import { useWorkspaceStore } from "@/lib/workspace/useWorkspaceStore";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

interface UntaggedFile {
  path: string;
  title: string;
}

export function UntaggedDashboard() {
  const [files, setFiles] = useState<UntaggedFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [bulkTagging, setBulkTagging] = useState(false);
  const [tagStats, setTagStats] = useState<{ domains: string[]; processes: string[]; tags: string[] } | null>(null);
  const openTab = useWorkspaceStore((s) => s.openTab);

  const fetchUntagged = useCallback(() => {
    setLoading(true);
    fetch("/api/metadata/untagged")
      .then((r) => r.json())
      .then((d) => { setFiles(d.files); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => { fetchUntagged(); }, [fetchUntagged]);

  useEffect(() => {
    fetch("/api/metadata/tags")
      .then((r) => r.json())
      .then(setTagStats)
      .catch(() => {});
  }, []);

  const handleBulkAutoTag = useCallback(async () => {
    setBulkTagging(true);
    let successCount = 0;
    for (const file of files) {
      try {
        // Fetch file content
        const wikiRes = await fetch(`/api/wiki/file/${encodeURIComponent(file.path)}`);
        if (!wikiRes.ok) continue;
        const wiki = await wikiRes.json();

        // Get AI suggestion
        const suggestRes = await fetch("/api/metadata/suggest", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: wiki.content, existing_tags: [] }),
        });
        if (!suggestRes.ok) continue;
        const suggestion = await suggestRes.json();

        // Build new frontmatter
        const raw = wiki.raw_content || "";
        const lines = raw.split("\n");
        let inFrontmatter = false;
        let frontmatterEnd = -1;

        for (let i = 0; i < lines.length; i++) {
          if (i === 0 && lines[i].trim() === "---") { inFrontmatter = true; continue; }
          if (inFrontmatter && lines[i].trim() === "---") { frontmatterEnd = i; break; }
        }

        // Simple approach: add tags to existing frontmatter or create new one
        const newTags = suggestion.tags || [];
        const newDomain = suggestion.domain || "";
        const newProcess = suggestion.process || "";

        let newContent: string;
        if (frontmatterEnd > 0) {
          // Insert metadata fields before closing ---
          const insertLines: string[] = [];
          if (newDomain && !raw.includes("domain:")) insertLines.push(`domain: "${newDomain}"`);
          if (newProcess && !raw.includes("process:")) insertLines.push(`process: "${newProcess}"`);
          if (newTags.length > 0 && !raw.includes("tags:")) {
            insertLines.push(`tags: [${newTags.map((t: string) => `"${t}"`).join(", ")}]`);
          }
          if (insertLines.length > 0) {
            lines.splice(frontmatterEnd, 0, ...insertLines);
          }
          newContent = lines.join("\n");
        } else {
          // Create frontmatter
          const fm = ["---"];
          if (newDomain) fm.push(`domain: "${newDomain}"`);
          if (newProcess) fm.push(`process: "${newProcess}"`);
          if (newTags.length > 0) fm.push(`tags: [${newTags.map((t: string) => `"${t}"`).join(", ")}]`);
          fm.push("---", "");
          newContent = fm.join("\n") + raw;
        }

        // Save
        await fetch(`/api/wiki/file/${encodeURIComponent(file.path)}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: newContent }),
        });
        successCount++;
      } catch {
        // Continue with next file
      }
    }
    setBulkTagging(false);
    toast.success(`${successCount}개 문서 자동 태깅 완료`);
    fetchUntagged();
  }, [files, fetchUntagged]);

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6">
      <div>
        <h2 className="text-lg font-bold">미태깅 문서 대시보드</h2>
        <p className="text-sm text-muted-foreground mt-1">
          메타데이터(Domain, Process, Tags)가 없는 문서 목록입니다.
        </p>
      </div>

      {/* Tag usage stats */}
      {tagStats && (
        <div className="grid grid-cols-3 gap-3">
          <div className="border rounded-lg p-3 text-center">
            <div className="text-2xl font-bold">{tagStats.domains.length}</div>
            <div className="text-xs text-muted-foreground">Domains</div>
          </div>
          <div className="border rounded-lg p-3 text-center">
            <div className="text-2xl font-bold">{tagStats.processes.length}</div>
            <div className="text-xs text-muted-foreground">Processes</div>
          </div>
          <div className="border rounded-lg p-3 text-center">
            <div className="text-2xl font-bold">{tagStats.tags.length}</div>
            <div className="text-xs text-muted-foreground">Tags</div>
          </div>
        </div>
      )}

      {/* Untagged files */}
      <div className="border rounded-lg">
        <div className="flex items-center justify-between px-4 py-3 border-b">
          <span className="text-sm font-medium">
            미태깅 문서 ({loading ? "..." : files.length}건)
          </span>
          <div className="flex gap-2">
            <button
              onClick={fetchUntagged}
              className="px-2 py-1 text-xs rounded border hover:bg-muted"
            >
              새로고침
            </button>
            {files.length > 0 && (
              <button
                onClick={handleBulkAutoTag}
                disabled={bulkTagging}
                className="px-3 py-1 text-xs rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 flex items-center gap-1"
              >
                {bulkTagging && <Loader2 className="h-3 w-3 animate-spin" />}
                {bulkTagging ? "태깅 중..." : "일괄 자동 태깅"}
              </button>
            )}
          </div>
        </div>
        {loading ? (
          <div className="p-4 text-sm text-muted-foreground text-center">로딩 중...</div>
        ) : files.length === 0 ? (
          <div className="p-4 text-sm text-muted-foreground text-center">
            모든 문서에 메타데이터가 설정되어 있습니다
          </div>
        ) : (
          <div className="divide-y">
            {files.map((f) => (
              <button
                key={f.path}
                onClick={() => openTab(f.path)}
                className="w-full text-left px-4 py-2 hover:bg-muted/50 text-sm flex items-center justify-between"
              >
                <span>{f.title}</span>
                <span className="text-xs text-muted-foreground">{f.path}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
