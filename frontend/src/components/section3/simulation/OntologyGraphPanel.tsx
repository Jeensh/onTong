"use client";

/**
 * 우측 패널 — ontology graph + 통계.
 *
 * target_selected 게이트 도착 시 backend /graph/{sid} 호출하여
 * target method 중심 1-hop graph 표시. 노드 / 엣지 / 통계.
 */
import { useEffect, useState } from "react";
import { Network, Loader2 } from "lucide-react";
import { simulationApi, type GraphResponse } from "@/lib/section3/simulation";

interface Props {
  sessionId: string | null;
  refreshKey: number; // decisions 길이 변화 시 재요청
}

const NODE_COLOR: Record<string, string> = {
  term: "bg-blue-100 border-blue-400 text-blue-800",
  action: "bg-violet-100 border-violet-400 text-violet-800",
  code_method: "bg-emerald-100 border-emerald-400 text-emerald-800",
  code_type: "bg-amber-100 border-amber-400 text-amber-800",
  rule: "bg-rose-100 border-rose-400 text-rose-800",
};

export function OntologyGraphPanel({ sessionId, refreshKey }: Props) {
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) {
      setGraph(null);
      return;
    }
    setLoading(true);
    setError(null);
    simulationApi.graph(sessionId)
      .then(setGraph)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [sessionId, refreshKey]);

  return (
    <>
      <div className="flex items-center gap-2">
        <Network size={14} className="text-emerald-600" />
        <h3 className="text-sm font-semibold text-gray-700">온톨로지 그래프</h3>
        {loading && <Loader2 size={11} className="animate-spin text-gray-400" />}
        {graph && <span className="text-[10px] text-gray-400 ml-auto">{graph.note}</span>}
      </div>

      {!sessionId && (
        <div className="text-xs text-gray-500 border border-dashed border-gray-300 rounded p-4 text-center">
          질문을 보내면 선택된 메서드 중심의<br />호출·용어 관계가 표시됩니다.
        </div>
      )}

      {error && (
        <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2">
          {error}
        </div>
      )}

      {graph && graph.nodes.length === 0 && (
        <div className="text-xs text-gray-500 border border-dashed border-gray-300 rounded p-3">
          {graph.note || "아직 노드가 없습니다 — 후보를 선택해 보세요"}
        </div>
      )}

      {graph && graph.nodes.length > 0 && (
        <>
          <div className="text-[11px] text-gray-600 truncate">
            <strong>중심 메서드</strong>{" "}
            <code className="text-emerald-700">{graph.target_fqn.split(".").pop()}</code>
          </div>

          {/* 노드 그룹 (지금은 표 형태 — 추후 xyflow 도입 시 교체) */}
          <div className="space-y-2 overflow-y-auto">
            {Object.entries(_groupByKind(graph.nodes)).map(([kind, nodes]) => (
              <div key={kind}>
                <div className="text-[10px] text-gray-500 mb-1 uppercase tracking-wide">{kind}</div>
                <div className="flex flex-wrap gap-1.5">
                  {nodes.map((n) => (
                    <span
                      key={n.id}
                      title={n.id}
                      className={"text-[10px] px-1.5 py-1 rounded border font-mono truncate max-w-[160px] " + NODE_COLOR[n.kind]}
                    >
                      {n.label}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div>
            <div className="text-[10px] text-gray-500 mb-1 uppercase tracking-wide">edges ({graph.edges.length})</div>
            <ul className="text-[10px] space-y-0.5 max-h-32 overflow-y-auto">
              {graph.edges.slice(0, 30).map((e, i) => (
                <li key={i} className="font-mono text-gray-700">
                  <span className="text-gray-500">{e.source.split(".").pop()?.slice(0, 24)}</span>
                  <span className="mx-1 text-amber-700">[{e.kind}]→</span>
                  <span className="text-gray-700">{e.target.split(".").pop()?.slice(0, 24)}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="border-t border-gray-200 pt-2 mt-2 text-[10px] text-gray-500">
            <strong>활용</strong>: 변경 시 영향 전파를 추적하려면 callers 따라 위로,
            구현체 보려면 callees 따라 아래로 탐색합니다.
          </div>
        </>
      )}
    </>
  );
}

function _groupByKind<T extends { kind: string }>(arr: T[]): Record<string, T[]> {
  const out: Record<string, T[]> = {};
  for (const n of arr) (out[n.kind] ||= []).push(n);
  return out;
}
