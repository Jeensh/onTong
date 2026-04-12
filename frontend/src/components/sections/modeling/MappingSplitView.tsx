"use client";

import React, { useCallback, useEffect, useState } from "react";
import { GitCompare, AlertTriangle, Loader2, Plus } from "lucide-react";
import {
  getCodeGraph,
  getOntologyTree,
  getMappings,
  addMapping,
  getMappingGaps,
  type CodeEntity,
  type DomainNode,
  type MappingEntry,
} from "@/lib/api/modeling";

const STATUS_BADGE: Record<string, string> = {
  draft: "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400",
  review: "bg-amber-100 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400",
  confirmed: "bg-green-100 dark:bg-green-950/40 text-green-700 dark:text-green-400",
};

export function MappingSplitView({ repoId }: { repoId: string }) {
  const [codeEntities, setCodeEntities] = useState<CodeEntity[]>([]);
  const [domainNodes, setDomainNodes] = useState<DomainNode[]>([]);
  const [mappings, setMappings] = useState<MappingEntry[]>([]);
  const [gapsCount, setGapsCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Add mapping form
  const [showAddForm, setShowAddForm] = useState(false);
  const [selectedCode, setSelectedCode] = useState("");
  const [selectedDomain, setSelectedDomain] = useState("");
  const [owner, setOwner] = useState("");
  const [adding, setAdding] = useState(false);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [codeData, ontologyData, mappingData, gapsData] = await Promise.all([
        getCodeGraph(repoId),
        getOntologyTree(),
        getMappings(repoId),
        getMappingGaps(repoId),
      ]);
      setCodeEntities(codeData.entities);
      setDomainNodes(ontologyData.nodes);
      setMappings(mappingData.mappings);
      setGapsCount(gapsData.count);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [repoId]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const handleAddMapping = async () => {
    if (!selectedCode || !selectedDomain || !owner.trim()) return;
    setAdding(true);
    setError(null);
    try {
      await addMapping(repoId, selectedCode, selectedDomain, owner.trim());
      setSelectedCode("");
      setSelectedDomain("");
      setOwner("");
      setShowAddForm(false);
      await fetchAll();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setAdding(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin mr-2" />
        Loading...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold mb-1">Mapping Management</h2>
          <p className="text-sm text-muted-foreground">Code entity to domain node mappings</p>
        </div>
        <div className="flex items-center gap-2">
          {gapsCount > 0 && (
            <span className="inline-flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400 bg-amber-100 dark:bg-amber-950/40 px-2.5 py-1 rounded-full">
              <AlertTriangle className="h-3 w-3" />
              {gapsCount} unmapped
            </span>
          )}
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Plus className="h-3.5 w-3.5" />
            Add Mapping
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-950/20 p-3 text-sm text-red-700 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Add mapping form */}
      {showAddForm && (
        <div className="rounded-lg border border-border bg-card p-4 space-y-3">
          <p className="text-sm font-medium">Add New Mapping</p>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-xs text-muted-foreground">Code Entity</label>
              <select
                value={selectedCode}
                onChange={(e) => setSelectedCode(e.target.value)}
                className="w-full mt-1 px-2 py-1.5 text-sm bg-background border border-border rounded"
              >
                <option value="">Select...</option>
                {codeEntities.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.name} ({e.kind})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Domain Node</label>
              <select
                value={selectedDomain}
                onChange={(e) => setSelectedDomain(e.target.value)}
                className="w-full mt-1 px-2 py-1.5 text-sm bg-background border border-border rounded"
              >
                <option value="">Select...</option>
                {domainNodes.map((n) => (
                  <option key={n.id} value={n.id}>
                    {n.name} ({n.kind})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Owner</label>
              <input
                type="text"
                value={owner}
                onChange={(e) => setOwner(e.target.value)}
                placeholder="team-name"
                className="w-full mt-1 px-2 py-1.5 text-sm bg-background border border-border rounded"
              />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <button
              onClick={() => setShowAddForm(false)}
              className="px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground"
            >
              Cancel
            </button>
            <button
              onClick={handleAddMapping}
              disabled={adding || !selectedCode || !selectedDomain || !owner.trim()}
              className="inline-flex items-center gap-1 rounded-md bg-primary px-4 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {adding && <Loader2 className="h-3 w-3 animate-spin" />}
              Add
            </button>
          </div>
        </div>
      )}

      {/* Split view: Code | Mappings | Domain */}
      <div className="grid grid-cols-3 gap-4">
        {/* Left: Code Entities */}
        <div className="rounded-lg border border-border bg-card">
          <div className="px-4 py-2.5 border-b border-border bg-muted/30">
            <span className="text-sm font-medium">Code Entities</span>
            <span className="text-xs text-muted-foreground ml-2">({codeEntities.length})</span>
          </div>
          <div className="divide-y divide-border max-h-80 overflow-auto">
            {codeEntities.length === 0 && (
              <p className="text-xs text-muted-foreground p-4 text-center">No code entities</p>
            )}
            {codeEntities.map((e) => (
              <div key={e.id} className="px-3 py-2">
                <span className="text-sm font-mono">{e.name}</span>
                <span className="text-[10px] text-muted-foreground ml-1">({e.kind})</span>
              </div>
            ))}
          </div>
        </div>

        {/* Center: Mappings */}
        <div className="rounded-lg border border-border bg-card">
          <div className="px-4 py-2.5 border-b border-border bg-muted/30">
            <span className="text-sm font-medium">Mappings</span>
            <span className="text-xs text-muted-foreground ml-2">({mappings.length})</span>
          </div>
          <div className="divide-y divide-border max-h-80 overflow-auto">
            {mappings.length === 0 && (
              <p className="text-xs text-muted-foreground p-4 text-center">No mappings yet</p>
            )}
            {mappings.map((m, i) => (
              <div key={`${m.code}-${m.domain}-${i}`} className="px-3 py-2 space-y-1">
                <div className="flex items-center gap-1 text-xs">
                  <span className="font-mono truncate">{m.code}</span>
                  <GitCompare className="h-3 w-3 text-muted-foreground shrink-0" />
                  <span className="font-mono truncate">{m.domain}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-medium ${STATUS_BADGE[m.status] || STATUS_BADGE.draft}`}>
                    {m.status}
                  </span>
                  <span className="text-[10px] text-muted-foreground">{m.owner}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Domain Nodes */}
        <div className="rounded-lg border border-border bg-card">
          <div className="px-4 py-2.5 border-b border-border bg-muted/30">
            <span className="text-sm font-medium">Domain Nodes</span>
            <span className="text-xs text-muted-foreground ml-2">({domainNodes.length})</span>
          </div>
          <div className="divide-y divide-border max-h-80 overflow-auto">
            {domainNodes.length === 0 && (
              <p className="text-xs text-muted-foreground p-4 text-center">No domain nodes</p>
            )}
            {domainNodes.map((n) => (
              <div key={n.id} className="px-3 py-2">
                <span className="text-sm">{n.name}</span>
                <span className="text-[10px] text-muted-foreground ml-1">({n.kind})</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
