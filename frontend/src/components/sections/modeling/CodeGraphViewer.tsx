"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Code, FolderTree, Box, Braces, Loader2 } from "lucide-react";
import { parseRepo, getCodeGraph, type CodeEntity, type ParseResponse } from "@/lib/api/modeling";

const KIND_ICON: Record<string, React.ReactNode> = {
  package: <FolderTree className="h-3.5 w-3.5 text-yellow-500" />,
  class: <Box className="h-3.5 w-3.5 text-blue-500" />,
  method: <Braces className="h-3.5 w-3.5 text-green-500" />,
  field: <Code className="h-3.5 w-3.5 text-muted-foreground" />,
};

export function CodeGraphViewer({ repoId }: { repoId: string }) {
  const [repoUrl, setRepoUrl] = useState("");
  const [parsing, setParsing] = useState(false);
  const [parseResult, setParseResult] = useState<ParseResponse | null>(null);
  const [entities, setEntities] = useState<CodeEntity[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchGraph = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getCodeGraph(repoId);
      setEntities(data.entities);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [repoId]);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  const handleParse = async () => {
    if (!repoUrl.trim()) return;
    setParsing(true);
    setError(null);
    try {
      const result = await parseRepo({ repo_url: repoUrl.trim(), repo_id: repoId });
      setParseResult(result);
      await fetchGraph();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setParsing(false);
    }
  };

  // Group entities by kind
  const grouped = entities.reduce<Record<string, CodeEntity[]>>((acc, e) => {
    const kind = e.kind || "unknown";
    if (!acc[kind]) acc[kind] = [];
    acc[kind].push(e);
    return acc;
  }, {});

  const kindOrder = ["package", "class", "method", "field"];
  const sortedKinds = Object.keys(grouped).sort(
    (a, b) => (kindOrder.indexOf(a) === -1 ? 99 : kindOrder.indexOf(a)) - (kindOrder.indexOf(b) === -1 ? 99 : kindOrder.indexOf(b))
  );

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold mb-1">Code Graph</h2>
        <p className="text-sm text-muted-foreground">Java repository parsing and dependency graph</p>
      </div>

      {/* Parse form */}
      <div className="rounded-lg border border-border bg-card p-4 space-y-3">
        <label className="text-xs font-medium text-foreground">Repository URL</label>
        <div className="flex gap-2">
          <input
            type="text"
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
            placeholder="https://github.com/org/repo.git"
            className="flex-1 px-3 py-1.5 text-sm bg-background border border-border rounded"
          />
          <button
            onClick={handleParse}
            disabled={parsing || !repoUrl.trim()}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {parsing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Code className="h-3.5 w-3.5" />}
            Parse Repository
          </button>
        </div>
      </div>

      {/* Parse result */}
      {parseResult && (
        <div className="rounded-lg border border-green-300 dark:border-green-800 bg-green-50 dark:bg-green-950/20 p-3 text-sm">
          <p className="font-medium text-green-700 dark:text-green-400">Parsing complete</p>
          <p className="text-xs text-muted-foreground mt-1">
            Files: {parseResult.files_parsed} | Entities: {parseResult.entities_count} | Relations: {parseResult.relations_count}
          </p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-950/20 p-3 text-sm text-red-700 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-12 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin mr-2" />
          Loading...
        </div>
      )}

      {/* Entity count summary */}
      {!loading && entities.length > 0 && (
        <>
          <div className="flex gap-3 flex-wrap">
            {sortedKinds.map((kind) => (
              <div key={kind} className="flex items-center gap-1.5 rounded-md border border-border bg-muted/50 px-3 py-1.5">
                {KIND_ICON[kind] || <Code className="h-3.5 w-3.5 text-muted-foreground" />}
                <span className="text-xs font-medium capitalize">{kind}</span>
                <span className="text-xs text-muted-foreground">({grouped[kind].length})</span>
              </div>
            ))}
            <div className="flex items-center gap-1.5 rounded-md border border-border bg-muted/50 px-3 py-1.5">
              <span className="text-xs font-medium">Total</span>
              <span className="text-xs text-muted-foreground">({entities.length})</span>
            </div>
          </div>

          {/* Entity tree grouped by kind */}
          <div className="space-y-4">
            {sortedKinds.map((kind) => (
              <div key={kind} className="rounded-lg border border-border bg-card">
                <div className="flex items-center gap-2 px-4 py-2.5 border-b border-border bg-muted/30">
                  {KIND_ICON[kind] || <Code className="h-3.5 w-3.5 text-muted-foreground" />}
                  <span className="text-sm font-medium capitalize">{kind}</span>
                  <span className="text-xs text-muted-foreground">({grouped[kind].length})</span>
                </div>
                <div className="divide-y divide-border max-h-64 overflow-auto">
                  {grouped[kind].map((entity) => (
                    <div key={entity.id} className="px-4 py-2 flex items-center justify-between">
                      <div>
                        <span className="text-sm font-mono">{entity.name}</span>
                        {entity.parent && (
                          <span className="text-xs text-muted-foreground ml-2">
                            &larr; {entity.parent}
                          </span>
                        )}
                      </div>
                      <span className="text-[11px] text-muted-foreground truncate max-w-48" title={entity.file_path}>
                        {entity.file_path}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Empty state */}
      {!loading && !error && entities.length === 0 && !parseResult && (
        <div className="text-center py-12 text-muted-foreground space-y-2">
          <Code className="h-8 w-8 mx-auto mb-2 opacity-30" />
          <p className="text-sm">No code entities found for this repository.</p>
          <p className="text-xs">Parse a repository above to generate the code graph.</p>
        </div>
      )}
    </div>
  );
}
