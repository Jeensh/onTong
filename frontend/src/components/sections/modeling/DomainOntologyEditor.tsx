"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Network, Plus, Loader2, ChevronRight, ChevronDown } from "lucide-react";
import { loadTemplate, getOntologyTree, addDomainNode, type DomainNode } from "@/lib/api/modeling";

interface TreeNode extends DomainNode {
  children: TreeNode[];
  expanded: boolean;
}

function buildTree(nodes: DomainNode[]): TreeNode[] {
  const map = new Map<string, TreeNode>();
  const roots: TreeNode[] = [];

  for (const node of nodes) {
    map.set(node.id, { ...node, children: [], expanded: true });
  }

  for (const node of nodes) {
    const treeNode = map.get(node.id)!;
    if (node.parent_id && map.has(node.parent_id)) {
      map.get(node.parent_id)!.children.push(treeNode);
    } else {
      roots.push(treeNode);
    }
  }

  return roots;
}

function TreeItem({ node, depth }: { node: TreeNode; depth: number }) {
  const [expanded, setExpanded] = useState(node.expanded);
  const hasChildren = node.children.length > 0;

  return (
    <div>
      <div
        className="flex items-center gap-1 py-1 px-2 hover:bg-muted/50 rounded cursor-pointer"
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
        onClick={() => hasChildren && setExpanded(!expanded)}
      >
        {hasChildren ? (
          expanded ? (
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          )
        ) : (
          <span className="w-3.5 shrink-0" />
        )}
        <Network className="h-3.5 w-3.5 text-blue-500 shrink-0" />
        <span className="text-sm font-mono">{node.name}</span>
        <span className="text-[10px] text-muted-foreground ml-1">({node.kind})</span>
        {node.description && (
          <span className="text-[10px] text-muted-foreground ml-2 truncate max-w-48">
            {node.description}
          </span>
        )}
      </div>
      {expanded && hasChildren && (
        <div>
          {node.children.map((child) => (
            <TreeItem key={child.id} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

export function DomainOntologyEditor({ repoId }: { repoId: string }) {
  const [nodes, setNodes] = useState<DomainNode[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingTemplate, setLoadingTemplate] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Add node form
  const [showAddForm, setShowAddForm] = useState(false);
  const [newId, setNewId] = useState("");
  const [newName, setNewName] = useState("");
  const [newKind, setNewKind] = useState("process");
  const [newParentId, setNewParentId] = useState("");
  const [adding, setAdding] = useState(false);

  const fetchTree = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getOntologyTree();
      setNodes(data.nodes);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTree();
  }, [fetchTree]);

  const handleLoadTemplate = async () => {
    setLoadingTemplate(true);
    setError(null);
    try {
      const result = await loadTemplate();
      await fetchTree();
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoadingTemplate(false);
    }
  };

  const handleAddNode = async () => {
    if (!newId.trim() || !newName.trim()) return;
    setAdding(true);
    setError(null);
    try {
      await addDomainNode({
        id: newId.trim(),
        name: newName.trim(),
        kind: newKind,
        parent_id: newParentId.trim() || null,
      });
      setNewId("");
      setNewName("");
      setNewKind("process");
      setNewParentId("");
      setShowAddForm(false);
      await fetchTree();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setAdding(false);
    }
  };

  const tree = buildTree(nodes);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold mb-1">Domain Ontology</h2>
        <p className="text-sm text-muted-foreground">SCOR + ISA-95 process hierarchy</p>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        <button
          onClick={handleLoadTemplate}
          disabled={loadingTemplate}
          className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {loadingTemplate ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Network className="h-3.5 w-3.5" />}
          Load SCOR Template
        </button>
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="inline-flex items-center gap-1.5 rounded-md border border-border px-4 py-1.5 text-xs font-medium text-foreground hover:bg-accent"
        >
          <Plus className="h-3.5 w-3.5" />
          Add Node
        </button>
        <button
          onClick={fetchTree}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground hover:bg-accent disabled:opacity-50"
        >
          Refresh
        </button>
      </div>

      {/* Add node form */}
      {showAddForm && (
        <div className="rounded-lg border border-border bg-card p-4 space-y-3">
          <p className="text-sm font-medium">Add Domain Node</p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-muted-foreground">ID</label>
              <input
                type="text"
                value={newId}
                onChange={(e) => setNewId(e.target.value)}
                placeholder="e.g. scor.plan.demand"
                className="w-full mt-1 px-2 py-1.5 text-sm bg-background border border-border rounded"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Name</label>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Demand Planning"
                className="w-full mt-1 px-2 py-1.5 text-sm bg-background border border-border rounded"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Kind</label>
              <select
                value={newKind}
                onChange={(e) => setNewKind(e.target.value)}
                className="w-full mt-1 px-2 py-1.5 text-sm bg-background border border-border rounded"
              >
                <option value="process">Process</option>
                <option value="activity">Activity</option>
                <option value="task">Task</option>
                <option value="resource">Resource</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Parent ID (optional)</label>
              <input
                type="text"
                value={newParentId}
                onChange={(e) => setNewParentId(e.target.value)}
                placeholder="scor.plan"
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
              onClick={handleAddNode}
              disabled={adding || !newId.trim() || !newName.trim()}
              className="inline-flex items-center gap-1 rounded-md bg-primary px-4 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {adding && <Loader2 className="h-3 w-3 animate-spin" />}
              Add
            </button>
          </div>
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

      {/* Tree */}
      {!loading && nodes.length > 0 && (
        <div className="rounded-lg border border-border bg-card">
          <div className="px-4 py-2.5 border-b border-border bg-muted/30 flex items-center justify-between">
            <span className="text-sm font-medium">Ontology Tree</span>
            <span className="text-xs text-muted-foreground">{nodes.length} nodes</span>
          </div>
          <div className="py-1 max-h-[500px] overflow-auto">
            {tree.map((node) => (
              <TreeItem key={node.id} node={node} depth={0} />
            ))}
          </div>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && nodes.length === 0 && (
        <div className="text-center py-12 text-muted-foreground space-y-2">
          <Network className="h-8 w-8 mx-auto mb-2 opacity-30" />
          <p className="text-sm">No domain nodes found.</p>
          <p className="text-xs">Load the SCOR template or add nodes manually.</p>
        </div>
      )}
    </div>
  );
}
