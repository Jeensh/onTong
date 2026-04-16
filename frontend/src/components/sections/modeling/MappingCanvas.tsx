"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  Panel,
  Handle,
  Position,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import dagre from "@dagrejs/dagre";
import { Search, GripVertical, Circle } from "lucide-react";
import {
  getOntologyTree,
  getMappings,
  getCodeGraph,
  addMapping,
  type DomainNode,
  type MappingEntry,
  type CodeEntity,
} from "@/lib/api/modeling";

interface MappingCanvasProps {
  repoId: string;
  onDomainNodeClick?: (nodeId: string, mappedEntities: string[]) => void;
  onEntityClick?: (fqn: string) => void;
  highlightDomainNode?: string | null;
}

// ── Domain Node Component ──

interface DomainNodeData {
  label: string;
  description: string;
  kind: string;
  mappingCount: number;
  mappingStatus: "confirmed" | "draft" | "none";
  isHighlighted: boolean;
  [key: string]: unknown;
}

function DomainNodeComponent({ data }: NodeProps<Node<DomainNodeData>>) {
  const bgColor =
    data.mappingStatus === "confirmed"
      ? "bg-green-500/10 border-green-500/50"
      : data.mappingStatus === "draft"
      ? "bg-yellow-500/10 border-yellow-500/50"
      : "bg-muted/50 border-border";

  const highlight = data.isHighlighted ? "ring-2 ring-primary ring-offset-1" : "";

  return (
    <div className={`px-3 py-2 rounded-lg border-2 ${bgColor} ${highlight} min-w-[140px]`}>
      <Handle type="target" position={Position.Top} className="!bg-muted-foreground !w-2 !h-2" />
      <div className="text-xs font-medium text-foreground">{data.label}</div>
      {data.mappingCount > 0 && (
        <div className="text-[10px] text-muted-foreground mt-0.5">
          {data.mappingCount}개 코드 연결
        </div>
      )}
      <Handle type="source" position={Position.Bottom} className="!bg-muted-foreground !w-2 !h-2" />
    </div>
  );
}

const nodeTypes = { domain: DomainNodeComponent };

// ── Layout ──

function layoutGraph(
  nodes: Node<DomainNodeData>[],
  edges: Edge[]
): { nodes: Node<DomainNodeData>[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", nodesep: 60, ranksep: 80 });

  nodes.forEach((node) => {
    g.setNode(node.id, { width: 160, height: 50 });
  });
  edges.forEach((edge) => {
    g.setEdge(edge.source, edge.target);
  });

  dagre.layout(g);

  const layoutNodes = nodes.map((node) => {
    const pos = g.node(node.id);
    return { ...node, position: { x: pos.x - 80, y: pos.y - 25 } };
  });

  return { nodes: layoutNodes, edges };
}

// ── Entity Panel ──

interface EntityPanelProps {
  entities: CodeEntity[];
  mappings: MappingEntry[];
  filter: string;
  onFilterChange: (f: string) => void;
  onEntityClick: (fqn: string) => void;
  onDragStart: (e: React.DragEvent, fqn: string) => void;
}

function EntityPanel({
  entities,
  mappings,
  filter,
  onFilterChange,
  onEntityClick,
  onDragStart,
}: EntityPanelProps) {
  const mappingMap = useMemo(() => {
    const map = new Map<string, MappingEntry>();
    mappings.forEach((m) => map.set(m.code, m));
    return map;
  }, [mappings]);

  const filtered = useMemo(() => {
    const f = filter.toLowerCase();
    return entities.filter(
      (e) =>
        (e.kind === "class" || e.kind === "interface") &&
        (e.name.toLowerCase().includes(f) || e.id.toLowerCase().includes(f))
    );
  }, [entities, filter]);

  return (
    <div className="border-t border-border bg-background/80">
      <div className="flex items-center gap-2 px-3 py-1.5 border-b border-border">
        <span className="text-[11px] font-medium text-foreground">코드 엔티티</span>
        <div className="flex-1" />
        <div className="relative">
          <Search size={11} className="absolute left-1.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={filter}
            onChange={(e) => onFilterChange(e.target.value)}
            placeholder="검색..."
            className="pl-5 pr-2 py-0.5 text-[10px] w-28 bg-background border border-border rounded"
          />
        </div>
      </div>
      <div className="max-h-[200px] overflow-auto p-1">
        {filtered.map((entity) => {
          const mapping = mappingMap.get(entity.id);
          return (
            <div
              key={entity.id}
              draggable
              onDragStart={(e) => onDragStart(e, entity.id)}
              onClick={() => onEntityClick(entity.id)}
              className="flex items-center gap-2 px-2 py-1 rounded text-[11px] cursor-grab hover:bg-muted/50 group"
            >
              <GripVertical size={10} className="text-muted-foreground/40 group-hover:text-muted-foreground" />
              <Circle
                size={8}
                className={mapping ? "text-green-500 fill-green-500" : "text-red-400 fill-red-400"}
              />
              <span className="truncate flex-1 font-mono">{entity.name}</span>
              {mapping && (
                <span className="text-[9px] text-muted-foreground truncate max-w-[100px]">
                  {mapping.domain.split("/").pop()}
                </span>
              )}
            </div>
          );
        })}
        {filtered.length === 0 && (
          <p className="text-[10px] text-muted-foreground p-2">엔티티 없음</p>
        )}
      </div>
    </div>
  );
}

// ── Main Component ──

export function MappingCanvas({
  repoId,
  onDomainNodeClick,
  onEntityClick,
  highlightDomainNode,
}: MappingCanvasProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<DomainNodeData>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [domainNodes, setDomainNodes] = useState<DomainNode[]>([]);
  const [mappings, setMappings] = useState<MappingEntry[]>([]);
  const [codeEntities, setCodeEntities] = useState<CodeEntity[]>([]);
  const [entityFilter, setEntityFilter] = useState("");
  const [loading, setLoading] = useState(false);

  // Load data
  useEffect(() => {
    if (!repoId) return;
    setLoading(true);
    Promise.all([
      getOntologyTree(),
      getMappings(repoId),
      getCodeGraph(repoId),
    ])
      .then(([ontoRes, mapRes, codeRes]) => {
        setDomainNodes(ontoRes.nodes);
        setMappings(mapRes.mappings);
        setCodeEntities(codeRes.entities);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [repoId]);

  // Build graph from domain nodes + mappings
  useEffect(() => {
    if (domainNodes.length === 0) return;

    const mappingsByDomain = new Map<string, MappingEntry[]>();
    mappings.forEach((m) => {
      const list = mappingsByDomain.get(m.domain) || [];
      list.push(m);
      mappingsByDomain.set(m.domain, list);
    });

    const graphNodes: Node<DomainNodeData>[] = domainNodes.map((dn) => {
      const domainMappings = mappingsByDomain.get(dn.id) || [];
      const hasConfirmed = domainMappings.some((m) => m.status === "confirmed");
      return {
        id: dn.id,
        type: "domain",
        position: { x: 0, y: 0 },
        data: {
          label: dn.name,
          description: dn.description || "",
          kind: dn.kind,
          mappingCount: domainMappings.length,
          mappingStatus: domainMappings.length === 0 ? "none" : hasConfirmed ? "confirmed" : "draft",
          isHighlighted: dn.id === highlightDomainNode,
        },
      };
    });

    const graphEdges: Edge[] = domainNodes
      .filter((dn) => dn.parent_id)
      .map((dn) => ({
        id: `${dn.parent_id}-${dn.id}`,
        source: dn.parent_id!,
        target: dn.id,
        type: "smoothstep",
        style: { stroke: "hsl(var(--muted-foreground))", strokeWidth: 1 },
      }));

    const laid = layoutGraph(graphNodes, graphEdges);
    setNodes(laid.nodes);
    setEdges(laid.edges);
  }, [domainNodes, mappings, highlightDomainNode, setNodes, setEdges]);

  // Handle node click
  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      if (!onDomainNodeClick) return;
      const mapped = mappings
        .filter((m) => m.domain === node.id)
        .map((m) => m.code);
      onDomainNodeClick(node.id, mapped);
    },
    [mappings, onDomainNodeClick]
  );

  // Handle drop (create mapping)
  const handleDrop = useCallback(
    async (e: React.DragEvent) => {
      e.preventDefault();
      const entityFqn = e.dataTransfer.getData("application/entity-fqn");
      if (!entityFqn) return;

      // Find the domain node under the cursor via React Flow's internals
      const target = (e.target as HTMLElement).closest("[data-id]");
      const domainId = target?.getAttribute("data-id");
      if (!domainId) return;

      try {
        await addMapping(repoId, entityFqn, domainId, "user");
        // Refresh mappings
        const mapRes = await getMappings(repoId);
        setMappings(mapRes.mappings);
      } catch (err) {
        console.error("Failed to create mapping:", err);
      }
    },
    [repoId]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "link";
  }, []);

  const handleEntityDragStart = useCallback((e: React.DragEvent, fqn: string) => {
    e.dataTransfer.setData("application/entity-fqn", fqn);
    e.dataTransfer.effectAllowed = "link";
  }, []);

  const handleEntityClick = useCallback(
    (fqn: string) => {
      onEntityClick?.(fqn);
    },
    [onEntityClick]
  );

  if (loading) {
    return <div className="flex items-center justify-center h-full text-xs text-muted-foreground">로딩 중...</div>;
  }

  return (
    <div className="flex flex-col h-full">
      {/* Graph area */}
      <div className="flex-1 min-h-0" onDrop={handleDrop} onDragOver={handleDragOver}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={handleNodeClick}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          proOptions={{ hideAttribution: true }}
        >
          <Background />
          <Controls position="top-right" />
          <MiniMap
            position="bottom-right"
            nodeStrokeWidth={3}
            pannable
            zoomable
          />
          <Panel position="top-left">
            <div className="bg-background/80 backdrop-blur-sm rounded px-2 py-1 text-[10px] text-muted-foreground border border-border">
              도메인 노드에 코드 엔티티를 드래그하여 매핑
            </div>
          </Panel>
        </ReactFlow>
      </div>

      {/* Entity panel */}
      <EntityPanel
        entities={codeEntities}
        mappings={mappings}
        filter={entityFilter}
        onFilterChange={setEntityFilter}
        onEntityClick={handleEntityClick}
        onDragStart={handleEntityDragStart}
      />
    </div>
  );
}
