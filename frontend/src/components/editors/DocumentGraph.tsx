"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { forceRadial } from "d3-force";
import {
  Network,
  RefreshCw,
  Loader2,
  Focus,
  Eye,
  EyeOff,
  Maximize2,
  Search,
  X,
} from "lucide-react";
import { useWorkspaceStore } from "@/lib/workspace/useWorkspaceStore";
import type { GraphData, GraphNode, GraphEdge } from "@/types";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-full text-muted-foreground">
      <Loader2 className="h-5 w-5 animate-spin mr-2" />
      그래프 로딩 중...
    </div>
  ),
});

// ── Constants ────────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  approved: "#22c55e",
  review: "#3b82f6",
  draft: "#9ca3af",
  deprecated: "#ef4444",
};
const DEFAULT_NODE_COLOR = "#64748b";
const SKILL_NODE_COLOR = "#a855f7"; // purple for skill nodes

const EDGE_COLORS: Record<string, string> = {
  "wiki-link": "#94a3b8",
  supersedes: "#f97316",
  related: "#60a5fa",
  similar: "#f87171",
};

const EDGE_LABELS: Record<string, string> = {
  "wiki-link": "링크",
  supersedes: "계보",
  related: "관련",
  similar: "유사",
};

const EDGE_WIDTH: Record<string, number> = {
  "wiki-link": 0.8,
  supersedes: 1.8,
  related: 1.2,
  similar: 0.6,
};

const RING_SPACING = 120; // px between depth rings
const DIM_OPACITY = 0.08; // opacity for non-highlighted elements

// ── Types ────────────────────────────────────────────────────────────

interface FGNode extends GraphNode {
  x?: number;
  y?: number;
  _degree?: number;
  _depth?: number;
}

interface FGEdge {
  source: string | FGNode;
  target: string | FGNode;
  type: string;
}

interface FGGraphData {
  nodes: FGNode[];
  links: FGEdge[];
}

interface QuickSearchResult {
  path: string;
  title: string;
  score: number;
  domain?: string;
  status?: string;
}

// ── Component ────────────────────────────────────────────────────────

export function DocumentGraph() {
  const [graphData, setGraphData] = useState<FGGraphData>({ nodes: [], links: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const graphCenterPath = useWorkspaceStore((s) => s.graphCenterPath);
  const [centerPath, setCenterPath] = useState<string | null>(null);
  const [showSimilar, setShowSimilar] = useState(false);
  const [maxDepth, setMaxDepth] = useState(0);
  const [hoveredNode, setHoveredNode] = useState<FGNode | null>(null);
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    node: FGNode;
  } | null>(null);

  // Neighbor index for hover highlighting
  const [neighborMap, setNeighborMap] = useState<Map<string, Set<string>>>(new Map());

  // Search state
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<QuickSearchResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const graphRef = useRef<any>(undefined);
  const containerRef = useRef<HTMLDivElement>(null);
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const openTab = useWorkspaceStore((s) => s.openTab);

  // ── Hover highlight helpers ──────────────────────────────────────

  const isHighlighted = useCallback(
    (nodeId: string) => {
      if (!hoveredNode) return true; // no hover = everything visible
      if (hoveredNode.id === nodeId) return true;
      return neighborMap.get(hoveredNode.id)?.has(nodeId) ?? false;
    },
    [hoveredNode, neighborMap]
  );

  const isEdgeHighlighted = useCallback(
    (srcId: string, tgtId: string) => {
      if (!hoveredNode) return true;
      return hoveredNode.id === srcId || hoveredNode.id === tgtId;
    },
    [hoveredNode]
  );

  // ── Search with debounce ────────────────────────────────────────

  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }

    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    searchTimerRef.current = setTimeout(async () => {
      setSearchLoading(true);
      try {
        const res = await fetch(`/api/search/quick?q=${encodeURIComponent(searchQuery)}&limit=10`);
        if (res.ok) {
          const data: QuickSearchResult[] = await res.json();
          setSearchResults(data);
        }
      } catch {
        // ignore
      } finally {
        setSearchLoading(false);
      }
    }, 200);

    return () => {
      if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    };
  }, [searchQuery]);

  // ── Fetch graph data ──────────────────────────────────────────────

  const fetchGraph = useCallback(async () => {
    if (!centerPath) return;

    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set("center_path", centerPath);
      params.set("include_similar", String(showSimilar));

      const res = await fetch(`/api/search/graph?${params}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: GraphData = await res.json();

      // Compute degree, max depth, and neighbor map
      const degreeMap = new Map<string, number>();
      const neighbors = new Map<string, Set<string>>();
      for (const edge of data.edges) {
        degreeMap.set(edge.source, (degreeMap.get(edge.source) ?? 0) + 1);
        degreeMap.set(edge.target, (degreeMap.get(edge.target) ?? 0) + 1);

        if (!neighbors.has(edge.source)) neighbors.set(edge.source, new Set());
        if (!neighbors.has(edge.target)) neighbors.set(edge.target, new Set());
        neighbors.get(edge.source)!.add(edge.target);
        neighbors.get(edge.target)!.add(edge.source);
      }

      let mxDepth = 0;
      const fgData: FGGraphData = {
        nodes: data.nodes.map((n) => {
          if (n.depth > mxDepth) mxDepth = n.depth;
          return {
            ...n,
            _degree: degreeMap.get(n.id) ?? 0,
            _depth: n.depth,
          };
        }),
        links: data.edges.map((e) => ({
          source: e.source,
          target: e.target,
          type: e.type,
        })),
      };
      setMaxDepth(mxDepth);
      setNeighborMap(neighbors);
      setGraphData(fgData);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [centerPath, showSimilar]);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  // Sync store → local
  useEffect(() => {
    if (graphCenterPath) {
      setCenterPath((prev) => (prev === graphCenterPath ? prev : graphCenterPath));
    }
  }, [graphCenterPath]);

  // Apply radial force after graph loads
  useEffect(() => {
    const fg = graphRef.current;
    if (!fg || !graphData.nodes.length) return;

    // d3 radial force: push nodes to rings based on depth
    fg.d3Force("radial", null); // clear first
    fg.d3Force(
      "radial",
      forceRadial(
        (node: FGNode) => (node._depth ?? 0) * RING_SPACING,
        0,
        0
      ).strength(0.8)
    );
    // Reduce default charge to let radial force dominate
    fg.d3Force("charge")?.strength(-200);
    fg.d3ReheatSimulation();

    // Zoom to fit after simulation settles
    setTimeout(() => fg.zoomToFit?.(400, 60), 500);
  }, [graphData]);

  // Close context menu on click outside
  useEffect(() => {
    if (!contextMenu) return;
    const handler = () => setContextMenu(null);
    document.addEventListener("click", handler);
    return () => document.removeEventListener("click", handler);
  }, [contextMenu]);

  // ── Node rendering ────────────────────────────────────────────────

  const nodeCanvasObject = useCallback(
    (node: FGNode, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const label = node.title || node.id.split("/").pop()?.replace(".md", "") || node.id;
      const d = node._depth ?? 0;
      const isCentered = node.id === centerPath;
      const isHovered = hoveredNode?.id === node.id;
      const highlighted = isHighlighted(node.id);

      // Size: center is biggest, direct connections next, then decreasing
      const baseRadius = isCentered ? 10 : 4 + Math.min((node._degree ?? 0) * 0.5, 4);
      const depthScale = maxDepth > 0 ? Math.max(0.5, 1 - d * 0.12) : 1;
      const radius = baseRadius * depthScale;

      // Opacity: hover highlighting takes priority
      const opacity = highlighted ? (isCentered || isHovered ? 1.0 : 0.9) : DIM_OPACITY;

      const isSkill = node.node_type === "skill";
      const color = isSkill ? SKILL_NODE_COLOR : (STATUS_COLORS[node.status] ?? DEFAULT_NODE_COLOR);

      ctx.globalAlpha = opacity;

      // Node body — diamond shape for skills, circle for documents
      if (isSkill) {
        const s = radius * 1.3;
        const cx = node.x ?? 0;
        const cy = node.y ?? 0;
        ctx.beginPath();
        ctx.moveTo(cx, cy - s);
        ctx.lineTo(cx + s, cy);
        ctx.lineTo(cx, cy + s);
        ctx.lineTo(cx - s, cy);
        ctx.closePath();
        ctx.fillStyle = color;
        ctx.fill();
      } else {
        ctx.beginPath();
        ctx.arc(node.x ?? 0, node.y ?? 0, radius, 0, 2 * Math.PI);
        ctx.fillStyle = color;
        ctx.fill();
      }

      // Ring for center / hover / direct connections
      if (isCentered) {
        ctx.strokeStyle = "#facc15";
        ctx.lineWidth = 2.5 / globalScale;
        ctx.stroke();
      } else if (isHovered) {
        ctx.strokeStyle = "#a78bfa";
        ctx.lineWidth = 2 / globalScale;
        ctx.stroke();
      } else if (d === 1 && highlighted) {
        ctx.strokeStyle = color;
        ctx.lineWidth = 0.8 / globalScale;
        ctx.stroke();
      }

      // Label
      const showLabel =
        isCentered ||
        isHovered ||
        (highlighted && (d <= 2 || globalScale > 0.7)) ||
        globalScale > 1.2;
      if (showLabel) {
        const fontSize = Math.max(
          (isCentered ? 13 : isHovered ? 12 : 10) / globalScale,
          2
        );
        ctx.font = `${isCentered || isHovered ? "bold " : ""}${fontSize}px -apple-system, sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "top";
        ctx.fillStyle = isHovered ? "#f8fafc" : isCentered ? "#fef08a" : "#cbd5e1";
        ctx.globalAlpha = highlighted ? (isCentered || isHovered ? 1.0 : 0.8) : DIM_OPACITY;

        const maxLen = isCentered ? 30 : d <= 1 ? 20 : 16;
        const truncated = label.length > maxLen ? label.slice(0, maxLen - 1) + "…" : label;
        ctx.fillText(truncated, node.x ?? 0, (node.y ?? 0) + radius + 3);
      }

      ctx.globalAlpha = 1.0;
    },
    [centerPath, hoveredNode, maxDepth, isHighlighted]
  );

  // ── Edge rendering ────────────────────────────────────────────────

  const linkCanvasObject = useCallback(
    (link: FGEdge, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const src = link.source as FGNode;
      const tgt = link.target as FGNode;
      if (src.x == null || tgt.x == null || src.y == null || tgt.y == null) return;

      const srcId = typeof link.source === "string" ? link.source : src.id;
      const tgtId = typeof link.target === "string" ? link.target : tgt.id;
      const highlighted = isEdgeHighlighted(srcId, tgtId);

      const type = link.type as string;
      const opacity = highlighted ? 0.7 : DIM_OPACITY;

      ctx.globalAlpha = opacity;
      ctx.strokeStyle = EDGE_COLORS[type] ?? "#94a3b8";
      ctx.lineWidth = ((EDGE_WIDTH[type] ?? 1) * (highlighted ? 1.5 : 0.8)) / globalScale;

      // Curved edge: slight arc to reduce overlap
      const dx = tgt.x - src.x;
      const dy = tgt.y - src.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const curvature = Math.min(0.15, 20 / (dist + 1));
      const midX = (src.x + tgt.x) / 2 + dy * curvature;
      const midY = (src.y + tgt.y) / 2 - dx * curvature;

      ctx.beginPath();
      ctx.moveTo(src.x, src.y);
      ctx.quadraticCurveTo(midX, midY, tgt.x, tgt.y);
      ctx.stroke();

      // Arrow for supersedes
      if (type === "supersedes" && highlighted) {
        const t = 0.5;
        const arrowX = (1 - t) * (1 - t) * src.x + 2 * (1 - t) * t * midX + t * t * tgt.x;
        const arrowY = (1 - t) * (1 - t) * src.y + 2 * (1 - t) * t * midY + t * t * tgt.y;
        const tangentX = 2 * (1 - t) * (midX - src.x) + 2 * t * (tgt.x - midX);
        const tangentY = 2 * (1 - t) * (midY - src.y) + 2 * t * (tgt.y - midY);
        const angle = Math.atan2(tangentY, tangentX);
        const arrowLen = 7 / globalScale;

        ctx.fillStyle = EDGE_COLORS[type];
        ctx.beginPath();
        ctx.moveTo(arrowX + arrowLen * Math.cos(angle), arrowY + arrowLen * Math.sin(angle));
        ctx.lineTo(
          arrowX + arrowLen * Math.cos(angle - Math.PI * 0.75),
          arrowY + arrowLen * Math.sin(angle - Math.PI * 0.75)
        );
        ctx.lineTo(
          arrowX + arrowLen * Math.cos(angle + Math.PI * 0.75),
          arrowY + arrowLen * Math.sin(angle + Math.PI * 0.75)
        );
        ctx.fill();
      }

      // Edge type label on hover
      if (highlighted && hoveredNode && globalScale > 0.5) {
        const labelX = midX;
        const labelY = midY;
        const fontSize = Math.max(8 / globalScale, 2);
        ctx.font = `${fontSize}px -apple-system, sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.globalAlpha = 0.6;
        ctx.fillStyle = EDGE_COLORS[type] ?? "#94a3b8";
        ctx.fillText(EDGE_LABELS[type] ?? type, labelX, labelY);
      }

      ctx.globalAlpha = 1.0;
    },
    [isEdgeHighlighted, hoveredNode]
  );

  // ── Background: depth rings ───────────────────────────────────────

  const onRenderFramePre = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (ctx: CanvasRenderingContext2D, globalScale: number) => {
      if (maxDepth === 0 || !graphData.nodes.length) return;

      // Find center node position
      const centerNode = graphData.nodes.find((n) => n.id === centerPath);
      const cx = centerNode?.x ?? 0;
      const cy = centerNode?.y ?? 0;

      // Draw concentric ring guides
      for (let d = 1; d <= maxDepth; d++) {
        const r = d * RING_SPACING;
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, 2 * Math.PI);
        ctx.strokeStyle = "rgba(148, 163, 184, 0.06)";
        ctx.lineWidth = 1 / globalScale;
        ctx.stroke();

        // Depth label on ring
        if (globalScale > 0.3) {
          const fontSize = Math.max(9 / globalScale, 2);
          ctx.font = `${fontSize}px -apple-system, sans-serif`;
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillStyle = "rgba(148, 163, 184, 0.15)";
          ctx.fillText(`${d}단계`, cx, cy - r + 10 / globalScale);
        }
      }
    },
    [maxDepth, centerPath, graphData.nodes]
  );

  // ── Event handlers ────────────────────────────────────────────────

  const handleNodeClick = useCallback(
    (node: FGNode) => {
      openTab(node.id);
    },
    [openTab]
  );

  const handleNodeRightClick = useCallback(
    (node: FGNode, event: MouseEvent) => {
      event.preventDefault();
      setContextMenu({ x: event.clientX, y: event.clientY, node });
    },
    []
  );

  const handleSelectCenter = useCallback((path: string) => {
    setCenterPath(path);
    setSearchQuery("");
    setSearchResults([]);
  }, []);

  const handleZoomToFit = useCallback(() => {
    graphRef.current?.zoomToFit?.(400, 60);
  }, []);

  // ── Container size ────────────────────────────────────────────────

  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setDimensions({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // ── Render: Search-first landing ──────────────────────────────────

  if (!centerPath) {
    return (
      <div className="flex flex-col h-full bg-background">
        <div className="flex items-center gap-2 px-3 py-2 border-b shrink-0">
          <Network className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium">문서 관계 그래프</span>
        </div>

        <div className="flex-1 flex items-center justify-center">
          <div className="w-full max-w-md px-6 space-y-4">
            <div className="text-center space-y-2">
              <Network className="h-10 w-10 mx-auto text-muted-foreground/30" />
              <h3 className="text-sm font-medium">문서를 검색하세요</h3>
              <p className="text-xs text-muted-foreground">
                관계를 탐색할 문서를 선택하면 해당 문서 중심으로 연결된 관계를 시각화합니다.
              </p>
            </div>

            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                autoFocus
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="문서 제목, 경로, 키워드로 검색..."
                className="w-full h-10 pl-9 pr-4 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && searchResults.length > 0) {
                    handleSelectCenter(searchResults[0].path);
                  }
                }}
              />
              {searchLoading && (
                <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 animate-spin text-muted-foreground" />
              )}
            </div>

            {searchResults.length > 0 && (
              <div className="border rounded-lg overflow-hidden shadow-sm">
                {searchResults.filter((r, i, arr) => arr.findIndex((x) => x.path === r.path) === i).map((r) => (
                  <button
                    key={r.path}
                    onClick={() => handleSelectCenter(r.path)}
                    className="w-full text-left px-4 py-2.5 hover:bg-muted transition-colors flex items-center gap-3 border-b last:border-b-0"
                  >
                    <span
                      className="w-2.5 h-2.5 rounded-full shrink-0"
                      style={{ background: STATUS_COLORS[r.status ?? ""] ?? DEFAULT_NODE_COLOR }}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium truncate">{r.title}</div>
                      <div className="text-xs text-muted-foreground truncate">{r.path}</div>
                    </div>
                    {r.domain && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground shrink-0">
                        {r.domain}
                      </span>
                    )}
                  </button>
                ))}
              </div>
            )}

            {searchQuery.trim() && !searchLoading && searchResults.length === 0 && (
              <div className="text-center py-4 text-xs text-muted-foreground">
                검색 결과가 없습니다.
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // ── Render: Graph view ────────────────────────────────────────────

  return (
    <div className="flex flex-col h-full bg-background">
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-3 py-2 border-b shrink-0 flex-wrap">
        <Network className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-medium">문서 관계 그래프</span>

        <div className="h-4 w-px bg-border mx-1" />

        {/* Inline search */}
        <div className="relative">
          <div className="relative">
            <Search className="absolute left-1.5 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="문서 검색..."
              className="h-6 w-44 pl-6 pr-6 text-xs bg-muted rounded border border-input focus:outline-none focus:ring-1 focus:ring-primary"
              onKeyDown={(e) => {
                if (e.key === "Escape") setSearchQuery("");
                if (e.key === "Enter" && searchResults.length > 0) {
                  handleSelectCenter(searchResults[0].path);
                }
              }}
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="absolute right-1.5 top-1/2 -translate-y-1/2"
              >
                <X className="h-3 w-3 text-muted-foreground" />
              </button>
            )}
          </div>

          {searchQuery.trim() && searchResults.length > 0 && (
            <div className="absolute top-7 left-0 z-30 bg-popover border rounded-lg shadow-lg py-1 w-64 max-h-48 overflow-y-auto">
              {searchResults.filter((r, i, arr) => arr.findIndex((x) => x.path === r.path) === i).map((r) => (
                <button
                  key={r.path}
                  onClick={() => handleSelectCenter(r.path)}
                  className="w-full text-left px-3 py-1.5 text-xs hover:bg-muted transition-colors flex items-center gap-2"
                >
                  <span
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ background: STATUS_COLORS[r.status ?? ""] ?? DEFAULT_NODE_COLOR }}
                  />
                  <div className="min-w-0">
                    <div className="truncate font-medium">{r.title}</div>
                    <div className="truncate text-muted-foreground text-[10px]">{r.path}</div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="h-4 w-px bg-border mx-1" />

        {/* Similarity toggle */}
        <button
          onClick={() => setShowSimilar((v) => !v)}
          className={`flex items-center gap-1 px-2 py-0.5 rounded text-xs transition-colors ${
            showSimilar
              ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
              : "text-muted-foreground hover:bg-muted"
          }`}
          title="유사도 엣지 표시"
        >
          {showSimilar ? <Eye className="h-3 w-3" /> : <EyeOff className="h-3 w-3" />}
          유사도
        </button>

        <div className="h-4 w-px bg-border mx-1" />

        <button
          onClick={handleZoomToFit}
          className="p-1 rounded text-muted-foreground hover:bg-muted transition-colors"
          title="화면에 맞추기"
        >
          <Maximize2 className="h-3 w-3" />
        </button>
        <button
          onClick={fetchGraph}
          className="p-1 rounded text-muted-foreground hover:bg-muted transition-colors"
          title="새로고침"
        >
          <RefreshCw className="h-3 w-3" />
        </button>

        {/* Legend */}
        <div className="ml-auto flex items-center gap-3 text-[10px] text-muted-foreground">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full" style={{ background: "#22c55e" }} />승인
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full" style={{ background: "#3b82f6" }} />검토
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full" style={{ background: "#9ca3af" }} />초안
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full" style={{ background: "#ef4444" }} />폐기
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rotate-45" style={{ background: SKILL_NODE_COLOR, width: 8, height: 8 }} />스킬
          </span>
          <span className="text-muted-foreground/40">|</span>
          <span className="text-muted-foreground/60">호버로 관계 탐색</span>
        </div>
      </div>

      {/* Center path indicator */}
      <div className="flex items-center gap-2 px-3 py-1 bg-yellow-50 dark:bg-yellow-900/10 border-b text-xs">
        <Focus className="h-3 w-3 text-yellow-600" />
        <span className="text-yellow-700 dark:text-yellow-400">
          중심: <strong>{centerPath.split("/").pop()?.replace(".md", "")}</strong>
          {maxDepth > 0 && <span className="ml-1 font-normal"> · {graphData.nodes.length}개 문서, 최대 {maxDepth}단계</span>}
        </span>
        <button
          onClick={() => { setCenterPath(null); setGraphData({ nodes: [], links: [] }); }}
          className="ml-auto text-yellow-600 hover:underline"
        >
          다른 문서 검색
        </button>
      </div>

      {/* Graph */}
      <div ref={containerRef} className="flex-1 relative">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/80 z-10">
            <Loader2 className="h-5 w-5 animate-spin mr-2 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">그래프 로딩 중...</span>
          </div>
        )}

        {error && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center text-sm text-red-500">
              <p>그래프 로드 실패: {error}</p>
              <button onClick={fetchGraph} className="mt-2 text-primary hover:underline">
                다시 시도
              </button>
            </div>
          </div>
        )}

        {!loading && graphData.nodes.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center text-sm text-muted-foreground">
            이 문서와 연결된 다른 문서가 없습니다
          </div>
        )}

        {graphData.nodes.length > 0 && (
          <ForceGraph2D
            ref={graphRef}
            width={dimensions.width}
            height={dimensions.height}
            graphData={graphData}
            nodeId="id"
            nodeCanvasObject={nodeCanvasObject as unknown as (node: object, ctx: CanvasRenderingContext2D, scale: number) => void}
            nodePointerAreaPaint={(node: unknown, color: string, ctx: CanvasRenderingContext2D) => {
              const n = node as FGNode;
              const radius = 6 + Math.min((n._degree ?? 0) * 0.5, 4);
              ctx.fillStyle = color;
              ctx.beginPath();
              ctx.arc(n.x ?? 0, n.y ?? 0, radius + 3, 0, 2 * Math.PI);
              ctx.fill();
            }}
            linkCanvasObject={linkCanvasObject as unknown as (link: object, ctx: CanvasRenderingContext2D, scale: number) => void}
            onNodeClick={handleNodeClick as unknown as (node: object, event: MouseEvent) => void}
            onNodeRightClick={handleNodeRightClick as unknown as (node: object, event: MouseEvent) => void}
            onNodeHover={(node: unknown) => setHoveredNode((node as FGNode) ?? null)}
            onBackgroundClick={() => setHoveredNode(null)}
            onRenderFramePre={onRenderFramePre as unknown as (ctx: CanvasRenderingContext2D, scale: number) => void}
            backgroundColor="transparent"
            cooldownTicks={150}
            d3AlphaDecay={0.015}
            d3VelocityDecay={0.35}
            warmupTicks={50}
          />
        )}

        {/* Hover tooltip */}
        {hoveredNode && hoveredNode.x != null && (
          <div
            className="absolute pointer-events-none bg-popover border rounded-lg shadow-lg px-3 py-2 text-xs z-20 max-w-[260px]"
            style={{ left: "50%", top: 8, transform: "translateX(-50%)" }}
          >
            <div className="font-medium text-sm">{hoveredNode.title}</div>
            <div className="text-muted-foreground mt-0.5">{hoveredNode.id}</div>
            <div className="flex items-center gap-1.5 mt-1.5">
              {hoveredNode.status && (
                <span
                  className="px-1.5 py-0.5 rounded text-[10px] font-medium"
                  style={{
                    background: (STATUS_COLORS[hoveredNode.status] ?? DEFAULT_NODE_COLOR) + "20",
                    color: STATUS_COLORS[hoveredNode.status] ?? DEFAULT_NODE_COLOR,
                  }}
                >
                  {hoveredNode.status}
                </span>
              )}
              {hoveredNode.domain && (
                <span className="px-1.5 py-0.5 rounded bg-muted text-[10px]">
                  {hoveredNode.domain}
                </span>
              )}
              <span className="px-1.5 py-0.5 rounded bg-muted text-[10px]">
                {hoveredNode._depth === 0 ? "중심" : `${hoveredNode._depth}단계`}
              </span>
            </div>
            {hoveredNode.tags.length > 0 && (
              <div className="flex gap-1 mt-1.5 flex-wrap">
                {hoveredNode.tags.slice(0, 4).map((t) => (
                  <span key={t} className="px-1 py-0 rounded bg-muted text-[10px]">
                    {t}
                  </span>
                ))}
              </div>
            )}
            <div className="text-muted-foreground/60 mt-1.5 pt-1.5 border-t">
              직접 연결 {neighborMap.get(hoveredNode.id)?.size ?? 0}개
            </div>
          </div>
        )}

        {/* Context menu */}
        {contextMenu && (
          <div
            className="fixed bg-popover border rounded-lg shadow-lg py-1 z-50 min-w-[160px]"
            style={{ left: contextMenu.x, top: contextMenu.y }}
          >
            <button
              className="w-full text-left px-3 py-1.5 text-sm hover:bg-muted transition-colors"
              onClick={() => {
                openTab(contextMenu.node.id);
                setContextMenu(null);
              }}
            >
              새 탭에서 열기
            </button>
            <button
              className="w-full text-left px-3 py-1.5 text-sm hover:bg-muted transition-colors"
              onClick={() => {
                setCenterPath(contextMenu.node.id);
                setContextMenu(null);
              }}
            >
              이 문서 중심으로 보기
            </button>
          </div>
        )}

        {/* Bottom info */}
        {!loading && graphData.nodes.length > 0 && (
          <div className="absolute bottom-2 left-3 text-[10px] text-muted-foreground/50">
            {graphData.nodes.length}개 문서 · {graphData.links.length}개 연결 · 최대 {maxDepth}단계 · 노드 위에 마우스를 올려 관계 탐색
          </div>
        )}
      </div>
    </div>
  );
}
