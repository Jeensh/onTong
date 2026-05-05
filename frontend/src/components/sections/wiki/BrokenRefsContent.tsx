"use client";

import { useEffect, useState } from "react";

// Mirror backend RefKind enum values
const REF_KIND_LABEL: Record<number, string> = {
  1: "수퍼시드 (이전)",
  2: "수퍼시드됨 (이후)",
  3: "관련 문서 (frontmatter)",
  4: "본문 wikilink [[...]]",
  5: "본문 markdown link",
};

const REF_KIND_COLOR: Record<number, string> = {
  1: "bg-amber-100 text-amber-800 border-amber-200",
  2: "bg-amber-100 text-amber-800 border-amber-200",
  3: "bg-blue-100 text-blue-800 border-blue-200",
  4: "bg-purple-100 text-purple-800 border-purple-200",
  5: "bg-rose-100 text-rose-800 border-rose-200",
};

interface BrokenRef {
  source_path: string;
  target_path: string;
  kind: number;
  location: { offset: number; length: number; raw: string };
}

interface BrokenRefsResponse {
  items: BrokenRef[];
  count: number;
  limit: number;
  offset: number;
  warning?: string;
}

const PAGE_SIZE = 50;

export function BrokenRefsContent() {
  const [data, setData] = useState<BrokenRefsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [kindFilter, setKindFilter] = useState<number | null>(null);
  const [offset, setOffset] = useState(0);
  const [groupBySource, setGroupBySource] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      // Use relative /api/ path — proxied by Next.js to BACKEND_URL (next.config.ts)
      const params = new URLSearchParams({
        limit: String(PAGE_SIZE),
        offset: String(offset),
      });
      if (kindFilter !== null) params.set("kind", String(kindFilter));

      const headers: Record<string, string> = {};
      const userId =
        typeof window !== "undefined"
          ? localStorage.getItem("ontong_user_id") || "demo"
          : "demo";
      headers["X-User-Id"] = userId;

      const r = await fetch(`/api/wiki/broken-refs?${params}`, { headers });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const body: BrokenRefsResponse = await r.json();
      setData(body);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kindFilter, offset]);

  // Navigate back to main wiki view; ?file= query param is forward-compatible
  // for future URL-based file-open wiring in the workspace store.
  const openSource = (path: string) => {
    window.location.href = `/?file=${encodeURIComponent(path)}`;
  };

  // Build grouped view if requested
  const grouped =
    groupBySource && data
      ? data.items.reduce<Record<string, BrokenRef[]>>((acc, r) => {
          (acc[r.source_path] = acc[r.source_path] || []).push(r);
          return acc;
        }, {})
      : null;

  return (
    <div className="space-y-4">
      <Toolbar
        kindFilter={kindFilter}
        onKindChange={(k) => {
          setKindFilter(k);
          setOffset(0);
        }}
        groupBySource={groupBySource}
        onGroupChange={setGroupBySource}
        onRefresh={fetchData}
        loading={loading}
      />

      {error && (
        <div className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-700">
          API 호출 실패: {error}
        </div>
      )}

      {data?.warning && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-800">
          ⚠️ {data.warning}
          <pre className="mt-2 inline-block rounded bg-amber-100 px-2 py-1 font-mono text-xs">
            python -m backend.cli migrate refindex-build
          </pre>
        </div>
      )}

      {!loading && !error && data && data.items.length === 0 && !data.warning && (
        <div className="rounded-lg border border-emerald-300 bg-emerald-50 p-8 text-center">
          <p className="text-2xl">✅</p>
          <p className="mt-2 text-sm text-emerald-800">깨진 참조가 없습니다.</p>
        </div>
      )}

      {loading && !data && (
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-8 text-center text-sm text-slate-500">
          로딩 중...
        </div>
      )}

      {data && data.items.length > 0 && !grouped && (
        <FlatList items={data.items} onSourceClick={openSource} />
      )}

      {data && grouped && (
        <GroupedList grouped={grouped} onSourceClick={openSource} />
      )}

      {data && data.count > 0 && (
        <Pagination
          offset={offset}
          pageSize={PAGE_SIZE}
          itemsCount={data.items.length}
          totalCount={data.count}
          onPrev={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          onNext={() =>
            setOffset(
              data.items.length === PAGE_SIZE ? offset + PAGE_SIZE : offset
            )
          }
        />
      )}
    </div>
  );
}

function Toolbar(props: {
  kindFilter: number | null;
  onKindChange: (k: number | null) => void;
  groupBySource: boolean;
  onGroupChange: (g: boolean) => void;
  onRefresh: () => void;
  loading: boolean;
}) {
  const kinds: Array<[string, number | null]> = [
    ["전체", null],
    ["frontmatter", 3],
    ["wikilink", 4],
    ["md link", 5],
    ["수퍼시드", 1],
  ];
  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="flex flex-wrap gap-1">
        {kinds.map(([label, k]) => (
          <button
            key={label}
            type="button"
            onClick={() => props.onKindChange(k)}
            className={`rounded-md border px-3 py-1 text-xs ${
              props.kindFilter === k
                ? "border-slate-900 bg-slate-900 text-white"
                : "border-slate-300 bg-white text-slate-600 hover:bg-slate-50"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="ml-auto flex items-center gap-2 text-xs">
        <label className="flex items-center gap-1 cursor-pointer text-slate-600">
          <input
            type="checkbox"
            checked={props.groupBySource}
            onChange={(e) => props.onGroupChange(e.target.checked)}
          />
          source 문서별 그룹
        </label>
        <button
          type="button"
          onClick={props.onRefresh}
          disabled={props.loading}
          className="rounded-md border border-slate-300 bg-white px-3 py-1 text-xs hover:bg-slate-50 disabled:opacity-50"
        >
          {props.loading ? "..." : "새로고침"}
        </button>
      </div>
    </div>
  );
}

function FlatList({
  items,
  onSourceClick,
}: {
  items: BrokenRef[];
  onSourceClick: (p: string) => void;
}) {
  return (
    <ul className="divide-y rounded-lg border border-slate-200 bg-white">
      {items.map((r, i) => (
        <li key={i} className="flex items-start gap-3 px-4 py-3 hover:bg-slate-50">
          <KindBadge kind={r.kind} />
          <div className="min-w-0 flex-1">
            <button
              type="button"
              onClick={() => onSourceClick(r.source_path)}
              className="block w-full truncate text-left font-medium text-slate-900 hover:underline"
              title={r.source_path}
            >
              {r.source_path}
            </button>
            <p className="mt-1 truncate text-xs text-slate-500">
              참조 대상 (없음):{" "}
              <span className="font-mono text-rose-600">{r.target_path}</span>
              <span className="ml-2 text-slate-400">offset {r.location.offset}</span>
            </p>
          </div>
        </li>
      ))}
    </ul>
  );
}

function GroupedList({
  grouped,
  onSourceClick,
}: {
  grouped: Record<string, BrokenRef[]>;
  onSourceClick: (p: string) => void;
}) {
  const sources = Object.keys(grouped).sort();
  return (
    <div className="space-y-3">
      {sources.map((src) => (
        <div key={src} className="rounded-lg border border-slate-200 bg-white">
          <button
            type="button"
            onClick={() => onSourceClick(src)}
            className="flex w-full items-center justify-between border-b border-slate-200 px-4 py-2 text-left hover:bg-slate-50"
          >
            <span className="truncate font-medium">{src}</span>
            <span className="ml-2 shrink-0 text-xs text-slate-500">
              {grouped[src].length} broken
            </span>
          </button>
          <ul className="divide-y">
            {grouped[src].map((r, i) => (
              <li key={i} className="flex items-start gap-3 px-4 py-2 text-sm">
                <KindBadge kind={r.kind} />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-mono text-rose-600">{r.target_path}</p>
                  <p className="text-xs text-slate-400">offset {r.location.offset}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function KindBadge({ kind }: { kind: number }) {
  const cls =
    REF_KIND_COLOR[kind] ?? "bg-slate-100 text-slate-700 border-slate-200";
  const label = REF_KIND_LABEL[kind] ?? `kind ${kind}`;
  return (
    <span
      className={`shrink-0 rounded border px-2 py-0.5 text-[10px] font-medium ${cls}`}
    >
      {label}
    </span>
  );
}

function Pagination(props: {
  offset: number;
  pageSize: number;
  itemsCount: number;
  totalCount: number;
  onPrev: () => void;
  onNext: () => void;
}) {
  const start = props.offset + 1;
  const end = props.offset + props.itemsCount;
  return (
    <div className="flex items-center justify-between text-xs text-slate-600">
      <span>
        {props.itemsCount > 0 ? `${start}–${end} / ${props.totalCount}` : "0"} 항목
      </span>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={props.onPrev}
          disabled={props.offset === 0}
          className="rounded-md border border-slate-300 bg-white px-3 py-1 hover:bg-slate-50 disabled:opacity-30"
        >
          이전
        </button>
        <button
          type="button"
          onClick={props.onNext}
          disabled={props.itemsCount < props.pageSize}
          className="rounded-md border border-slate-300 bg-white px-3 py-1 hover:bg-slate-50 disabled:opacity-30"
        >
          다음
        </button>
      </div>
    </div>
  );
}
