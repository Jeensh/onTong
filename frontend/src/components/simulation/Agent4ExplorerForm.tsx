"use client";

import { useEffect, useState } from "react";
import {
  expandOntologyNode,
  fetchGraphStats,
  findOntologyPath,
  searchOntologyNodes,
  type GraphStats,
  type OntologyExpandResult,
  type OntologyPathResult,
  type OntologySearchResult,
} from "@/lib/simulation/agentApi";
import { OntologySubgraphView } from "./shared/OntologySubgraphView";

const GROUP_FILTERS = [
  { id: "term", label: "Term", color: "bg-amber-100 text-amber-800" },
  { id: "step", label: "Step", color: "bg-purple-100 text-purple-800" },
  { id: "standard", label: "SC", color: "bg-emerald-100 text-emerald-800" },
  { id: "method", label: "Method", color: "bg-blue-100 text-blue-800" },
  { id: "class", label: "Class", color: "bg-indigo-100 text-indigo-800" },
  { id: "table", label: "Table", color: "bg-cyan-100 text-cyan-800" },
  { id: "variable", label: "Variable", color: "bg-lime-100 text-lime-800" },
];

type TabKey = "search" | "path" | "stats";

export function Agent4ExplorerForm() {
  const [tab, setTab] = useState<TabKey>("search");

  // ── search state
  const [query, setQuery] = useState("Edging");
  const [groups, setGroups] = useState<string[]>([]);
  const [searchResult, setSearchResult] = useState<OntologySearchResult | null>(null);

  const [hops, setHops] = useState<1 | 2>(1);
  const [expanded, setExpanded] = useState<OntologyExpandResult | null>(null);

  // ── path state
  const [fromId, setFromId] = useState("term:term_edging");
  const [toId, setToId] = useState("step:2");
  const [pathResult, setPathResult] = useState<OntologyPathResult | null>(null);

  // ── stats
  const [stats, setStats] = useState<GraphStats | null>(null);

  useEffect(() => {
    fetchGraphStats().then(setStats).catch(() => setStats(null));
  }, []);

  const search = async () => {
    if (!query.trim()) return;
    const r = await searchOntologyNodes(query, groups.length ? groups : undefined);
    setSearchResult(r);
  };

  const expand = async (nodeId: string, h: 1 | 2 = hops) => {
    const r = await expandOntologyNode({ node_id: nodeId, hops: h });
    setExpanded(r);
    setHops(h);
  };

  const findPath = async () => {
    const r = await findOntologyPath({ from_id: fromId, to_id: toId, max_hops: 5 });
    setPathResult(r);
  };

  return (
    <div className="space-y-5">
      <h2 className="text-xl font-semibold text-gray-900">
        🌐 Agent 4 — 온톨로지 익스플로러
      </h2>

      <div className="rounded border border-fuchsia-200 bg-fuchsia-50 p-3 text-xs text-fuchsia-900">
        ✨ Neo4j의 Term/Step/Standard/Method/Class/Table 노드를 자유롭게 검색하고,
        1~2 hop 이웃을 expand하거나 두 노드 간 <b>shortest path</b>를 찾을 수 있습니다.
      </div>

      <div className="flex gap-1 rounded border border-gray-200 bg-white p-1 shadow-sm">
        {[
          { key: "search" as const, label: "🔍 노드 검색 + Expand" },
          { key: "path" as const, label: "🛤 두 노드 간 Path" },
          { key: "stats" as const, label: "📊 통계 대시보드" },
        ].map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex-1 rounded px-3 py-2 text-sm font-medium ${
              tab === t.key
                ? "bg-fuchsia-100 text-fuchsia-900"
                : "text-gray-600 hover:bg-gray-50"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "search" && (
        <SearchAndExpand
          query={query}
          setQuery={setQuery}
          groups={groups}
          setGroups={setGroups}
          searchResult={searchResult}
          search={search}
          expanded={expanded}
          hops={hops}
          expand={expand}
        />
      )}

      {tab === "path" && (
        <PathFinder
          fromId={fromId}
          setFromId={setFromId}
          toId={toId}
          setToId={setToId}
          result={pathResult}
          findPath={findPath}
        />
      )}

      {tab === "stats" && <StatsDashboard stats={stats} />}
    </div>
  );
}

// ─── Search + Expand ───────────────────────────────────────────────

function SearchAndExpand({
  query, setQuery, groups, setGroups, searchResult, search,
  expanded, hops, expand,
}: {
  query: string; setQuery: (v: string) => void;
  groups: string[]; setGroups: (v: string[]) => void;
  searchResult: OntologySearchResult | null;
  search: () => void;
  expanded: OntologyExpandResult | null;
  hops: 1 | 2;
  expand: (nodeId: string, h?: 1 | 2) => void;
}) {
  const toggleGroup = (g: string) => {
    setGroups(groups.includes(g) ? groups.filter((x) => x !== g) : [...groups, g]);
  };
  const trace = expanded?.trace;
  const seed = new Set(trace?.seed_ids ?? []);

  return (
    <div className="space-y-4">
      <div className="rounded border border-gray-200 bg-white p-5 shadow-sm">
        <label className="mb-1 block text-sm font-medium text-gray-700">노드 검색</label>
        <input
          type="text" value={query} onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
          className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
          placeholder="예: Edging / SC070 / 분할수 / SlabDesignService"
        />

        <div className="mt-3 flex flex-wrap gap-2 text-xs">
          <span className="self-center text-gray-500">필터:</span>
          {GROUP_FILTERS.map((g) => (
            <label
              key={g.id}
              className={`cursor-pointer rounded border px-2 py-0.5 ${
                groups.includes(g.id) ? `${g.color} border-current` : "border-gray-300 bg-gray-50 text-gray-500"
              }`}
            >
              <input
                type="checkbox" className="mr-1"
                checked={groups.includes(g.id)} onChange={() => toggleGroup(g.id)}
              />
              {g.label}
            </label>
          ))}
        </div>

        <button
          onClick={search}
          className="mt-3 rounded bg-fuchsia-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-fuchsia-700"
        >
          🔍 검색
        </button>
      </div>

      {searchResult && searchResult.nodes.length > 0 && (
        <div className="rounded border border-gray-200 bg-white shadow-sm">
          <div className="border-b border-gray-100 px-3 py-2 text-xs font-semibold text-gray-700">
            🎯 검색 결과 — {searchResult.nodes.length}개 노드 (클릭하면 1-hop 이웃 expand)
          </div>
          <ul className="max-h-64 divide-y divide-gray-100 overflow-y-auto">
            {searchResult.nodes.map((n) => (
              <li
                key={n.id}
                className="cursor-pointer px-3 py-2 hover:bg-fuchsia-50/50"
                onClick={() => expand(n.id, 1)}
              >
                <div className="flex items-center gap-2">
                  <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-mono uppercase text-gray-700">
                    {n.group}
                  </span>
                  <span className="text-sm font-medium text-gray-900">{n.label}</span>
                  <span className="font-mono text-[10px] text-gray-400">{n.id}</span>
                </div>
                {n.snippet && (
                  <div className="mt-0.5 text-xs text-gray-500 truncate">{n.snippet}</div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {expanded && trace && (
        <div>
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-gray-700">
              🌐 <code className="font-mono">{expanded.node_id}</code> 주변 — {hops}-hop expand
              ({trace.nodes.length} 노드 / {trace.edges.length} 관계)
            </h3>
            <div className="flex gap-1 rounded border border-gray-200 bg-white p-0.5">
              {[1, 2].map((h) => (
                <button
                  key={h}
                  onClick={() => expand(expanded.node_id, h as 1 | 2)}
                  className={`rounded px-2 py-0.5 text-xs ${
                    hops === h ? "bg-fuchsia-100 text-fuchsia-900 font-semibold" : "text-gray-600"
                  }`}
                >
                  {h}-hop
                </button>
              ))}
            </div>
          </div>
          <OntologySubgraphView
            nodes={trace.nodes} edges={trace.edges}
            highlightIds={seed}
            onNodeClick={(id) => expand(id, hops)}
            height={500}
          />
          <div className="mt-2 text-[10px] text-gray-500">
            💡 그래프 노드를 클릭하면 그 노드를 새 seed로 expand합니다.
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Path Finder ───────────────────────────────────────────────────

function PathFinder({
  fromId, setFromId, toId, setToId, result, findPath,
}: {
  fromId: string; setFromId: (v: string) => void;
  toId: string; setToId: (v: string) => void;
  result: OntologyPathResult | null;
  findPath: () => void;
}) {
  const trace = result?.trace;
  const seed = new Set(trace?.seed_ids ?? []);
  const path = new Set(trace?.path_edge_keys ?? []);

  return (
    <div className="space-y-4">
      <div className="rounded border border-gray-200 bg-white p-5 shadow-sm">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">From</label>
            <input
              type="text" value={fromId} onChange={(e) => setFromId(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm font-mono"
              placeholder="예: term:term_edging"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">To</label>
            <input
              type="text" value={toId} onChange={(e) => setToId(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm font-mono"
              placeholder="예: step:2 또는 method:SlabDesignService.calculatePrimaryWidthRange"
            />
          </div>
        </div>
        <button
          onClick={findPath}
          className="mt-4 rounded bg-fuchsia-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-fuchsia-700"
        >
          🛤 Shortest Path 검색
        </button>
        <div className="mt-2 text-[11px] text-gray-500">
          ID 형식: <code>step:2</code>, <code>standard:SC070</code>, <code>term:term_edging</code>,
          <code>method:&lt;id&gt;</code>, <code>class:&lt;name&gt;</code>, <code>table:&lt;name&gt;</code>
        </div>
      </div>

      {result && (
        <div>
          <h3 className="mb-2 text-sm font-semibold text-gray-700">
            {result.found ? "✅ 경로 발견" : "❌ 경로 없음 (max_hops 초과)"}
          </h3>
          {trace && trace.nodes.length > 0 && (
            <OntologySubgraphView
              nodes={trace.nodes} edges={trace.edges}
              highlightIds={seed} pathEdgeKeys={path}
              height={420}
            />
          )}
        </div>
      )}
    </div>
  );
}

// ─── Stats Dashboard ──────────────────────────────────────────────

function StatsDashboard({ stats }: { stats: GraphStats | null }) {
  if (!stats) {
    return (
      <div className="rounded border border-gray-200 bg-white p-6 text-sm text-gray-500">
        통계 로드 중...
      </div>
    );
  }

  const layers = [
    {
      title: "Layer 1 — Business",
      color: "from-amber-50 to-amber-100",
      items: [
        ["Term", stats.nodes.Term ?? 0],
        ["TermCategory", stats.nodes.TermCategory ?? 0],
      ],
    },
    {
      title: "Layer 2 — Process",
      color: "from-purple-50 to-purple-100",
      items: [
        ["Step", stats.nodes.Step ?? 0],
        ["Standard", stats.nodes.Standard ?? 0],
        ["Variable", stats.nodes.Variable ?? 0],
        ["ErrorCode", stats.nodes.ErrorCode ?? 0],
      ],
    },
    {
      title: "Layer 3 — Code",
      color: "from-blue-50 to-blue-100",
      items: [
        ["Class", stats.nodes.Class ?? 0],
        ["Method", stats.nodes.Method ?? 0],
        ["Table", stats.nodes.Table ?? 0],
      ],
    },
  ];

  const relations = Object.entries(stats.relations).sort((a, b) => b[1] - a[1]);

  return (
    <div className="space-y-4">
      <div className="rounded border border-gray-200 bg-white p-4 shadow-sm">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded bg-fuchsia-50 p-3">
            <div className="text-[10px] uppercase text-fuchsia-700">총 노드</div>
            <div className="text-2xl font-bold text-fuchsia-900">{stats.totals.nodes}</div>
          </div>
          <div className="rounded bg-blue-50 p-3">
            <div className="text-[10px] uppercase text-blue-700">총 관계</div>
            <div className="text-2xl font-bold text-blue-900">{stats.totals.relations}</div>
          </div>
          <div className="rounded bg-emerald-50 p-3">
            <div className="text-[10px] uppercase text-emerald-700">관계 종류</div>
            <div className="text-2xl font-bold text-emerald-900">{relations.length}</div>
          </div>
          <div className="rounded bg-amber-50 p-3">
            <div className="text-[10px] uppercase text-amber-700">노드 라벨</div>
            <div className="text-2xl font-bold text-amber-900">
              {Object.keys(stats.nodes).length}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        {layers.map((l) => (
          <div
            key={l.title}
            className={`rounded border border-gray-200 bg-gradient-to-br ${l.color} p-4`}
          >
            <div className="mb-2 text-sm font-semibold text-gray-900">{l.title}</div>
            <ul className="space-y-1">
              {l.items.map(([k, v]) => (
                <li key={k} className="flex items-center justify-between text-xs">
                  <span className="text-gray-700">{k}</span>
                  <span className="font-mono font-bold text-gray-900">{v}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="rounded border border-gray-200 bg-white p-4 shadow-sm">
        <div className="mb-3 text-sm font-semibold text-gray-900">관계 타입 분포</div>
        <div className="space-y-1.5">
          {relations.map(([k, v]) => {
            const max = relations[0][1] || 1;
            const pct = (v / max) * 100;
            return (
              <div key={k} className="flex items-center gap-3">
                <span className="w-44 truncate font-mono text-xs text-gray-700">{k}</span>
                <div className="flex-1 rounded bg-gray-100">
                  <div
                    className="h-4 rounded bg-fuchsia-400"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className="w-10 text-right text-xs font-mono">{v}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
