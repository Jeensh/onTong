"use client";

import { useEffect, useRef, useCallback } from "react";
import type { OntologyGraphData, GraphState, OntologyNode } from "@/lib/simulation/types";

interface OntologyGraphProps {
  graphData: OntologyGraphData | null;
  highlight: GraphState;
  onNodeClick?: (node: OntologyNode) => void;
}

// Node colors by type
const NODE_COLORS: Record<string, string> = {
  Order: "#1565C0",
  ContinuousCaster: "#6A1B9A",
  HotRollingMill: "#E65100",
  EdgeSpec: "#2E7D32",
  Slab: "#37474F",
};

const NODE_SIZES: Record<string, number> = {
  Order: 10,
  ContinuousCaster: 12,
  HotRollingMill: 12,
  EdgeSpec: 9,
  Slab: 8,
};

// Status overlay colors
const STATUS_COLORS: Record<string, string> = {
  ERROR: "#ef4444",
  DESIGNED: "#22c55e",
  PENDING: "#f59e0b",
};

export function OntologyGraph({ graphData, highlight, onNodeClick }: OntologyGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<unknown>(null);
  const onNodeClickRef = useRef(onNodeClick);
  useEffect(() => { onNodeClickRef.current = onNodeClick; }, [onNodeClick]);

  const buildGraphData = useCallback(() => {
    if (!graphData) return { nodes: [], links: [] };

    const traversalSet = new Set(highlight.traversal);
    const highlightedEdges = new Set(
      highlight.highlighted_edges.map((e) => `${e.from}->${e.to}`)
    );

    const nodes = graphData.nodes.map((n) => ({
      id: n.id,
      label: n.label,
      type: n.type,
      status: n.status,
      color: traversalSet.has(n.id)
        ? "#FBBF24"
        : STATUS_COLORS[n.status ?? ""] ?? NODE_COLORS[n.type] ?? "#9E9E9E",
      size: NODE_SIZES[n.type] ?? 8,
      isHighlighted: traversalSet.has(n.id),
    }));

    const links = graphData.edges.map((e) => ({
      source: e.from,
      target: e.to,
      relation: e.relation,
      color: highlightedEdges.has(`${e.from}->${e.to}`)
        ? "#FBBF24"
        : "rgba(150,150,150,0.4)",
      width: highlightedEdges.has(`${e.from}->${e.to}`) ? 3 : 1,
    }));

    return { nodes, links };
  }, [graphData, highlight]);

  useEffect(() => {
    if (!containerRef.current || !graphData) return;

    // Dynamically import react-force-graph-2d (client only)
    let cancelled = false;
    import("react-force-graph-2d").then((module) => {
      if (cancelled || !containerRef.current) return;
      const ForceGraph2D = module.default;

      const data = buildGraphData();
      const container = containerRef.current;
      const width = container.clientWidth || 400;
      const height = container.clientHeight || 300;

      // Cleanup old instance
      if (graphRef.current) {
        container.innerHTML = "";
      }

      // Create a mount point
      const mountDiv = document.createElement("div");
      mountDiv.style.width = "100%";
      mountDiv.style.height = "100%";
      container.appendChild(mountDiv);

      import("react-dom/client").then(({ createRoot }) => {
        if (cancelled || !mountDiv) return;
        const root = createRoot(mountDiv);

        root.render(
          <ForceGraph2D
            graphData={data}
            width={width}
            height={height}
            backgroundColor="#0f172a"
            nodeLabel={(node: { label?: string; type?: string }) =>
              node.type === "Order"
                ? `${node.label ?? ""} (클릭하여 시뮬레이터에서 열기)`
                : (node.label ?? "")
            }
            nodeColor={(node: { color?: string }) => node.color ?? "#9E9E9E"}
            nodeRelSize={1}
            nodeVal={(node: { size?: number }) => node.size ?? 8}
            linkColor={(link: { color?: string }) => link.color ?? "rgba(150,150,150,0.4)"}
            linkWidth={(link: { width?: number }) => link.width ?? 1}
            linkDirectionalArrowLength={4}
            linkDirectionalArrowRelPos={1}
            linkLabel={(link: { relation?: string }) => link.relation ?? ""}
            onNodeClick={(node: { id?: string | number; type?: string; label?: string; status?: string }) => {
              if (node.type === "Order" && onNodeClickRef.current) {
                onNodeClickRef.current({
                  id: String(node.id ?? ""),
                  type: "Order",
                  label: node.label ?? "",
                  status: node.status,
                });
              }
            }}
            nodeCanvasObject={(
              node: { x?: number; y?: number; label?: string; color?: string; size?: number; isHighlighted?: boolean; type?: string },
              ctx: CanvasRenderingContext2D,
              globalScale: number
            ) => {
              const x = node.x ?? 0;
              const y = node.y ?? 0;
              const size = (node.size ?? 8) / 2;

              // Node circle
              ctx.beginPath();
              ctx.arc(x, y, size, 0, 2 * Math.PI);
              ctx.fillStyle = node.color ?? "#9E9E9E";
              ctx.fill();

              // Highlight ring (traversal)
              if (node.isHighlighted) {
                ctx.strokeStyle = "#FBBF24";
                ctx.lineWidth = 2;
                ctx.stroke();
              }

              // Order 노드: 클릭 가능 표시 (점선 링)
              if (node.type === "Order" && !node.isHighlighted) {
                ctx.setLineDash([2, 2]);
                ctx.strokeStyle = "rgba(255,255,255,0.3)";
                ctx.lineWidth = 1;
                ctx.stroke();
                ctx.setLineDash([]);
              }

              // Label
              const label = node.label ?? "";
              const fontSize = Math.max(8, 10 / globalScale);
              ctx.font = `${fontSize}px sans-serif`;
              ctx.fillStyle = "white";
              ctx.textAlign = "center";
              ctx.textBaseline = "middle";
              ctx.fillText(label, x, y + size + fontSize);
            }}
            cooldownTicks={100}
            d3VelocityDecay={0.3}
          />
        );

        graphRef.current = root;
      });
    });

    return () => {
      cancelled = true;
    };
  }, [graphData, highlight, buildGraphData]);

  if (!graphData) {
    return (
      <div
        ref={containerRef}
        className="w-full h-full flex items-center justify-center bg-slate-900 rounded"
      >
        <div className="text-center text-slate-400">
          <div className="text-2xl mb-2">🕸️</div>
          <p className="text-xs">온톨로지 그래프</p>
          <p className="text-[10px] mt-1 opacity-60">에이전트 실행 시 표시됩니다</p>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full h-full relative">
      {/* Legend */}
      <div className="absolute top-2 left-2 z-10 bg-slate-900/80 rounded p-2 text-[10px] space-y-1">
        {Object.entries(NODE_COLORS).map(([type, color]) => (
          <div key={type} className="flex items-center gap-1.5">
            <div
              className="w-2.5 h-2.5 rounded-full"
              style={{ backgroundColor: color }}
            />
            <span className="text-slate-300">{type}</span>
          </div>
        ))}
        {highlight.traversal.length > 0 && (
          <div className="flex items-center gap-1.5 border-t border-slate-600 pt-1 mt-1">
            <div className="w-2.5 h-2.5 rounded-full bg-yellow-400" />
            <span className="text-yellow-400">탐색 경로</span>
          </div>
        )}
      </div>
      <div ref={containerRef} className="w-full h-full" />
    </div>
  );
}
