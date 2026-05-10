"use client";

import { useState } from "react";
import {
  runAgent1,
  type Agent1Request,
  type Agent1Result,
  type ChangeKind,
  type ModificationType,
  type TargetType,
} from "@/lib/simulation/agentApi";
import { OntologySubgraphView } from "./shared/OntologySubgraphView";
import { ResultTable } from "./shared/ResultTable";

const TARGET_PRESETS: Record<string, { id: string; label: string }[]> = {
  table: [
    { id: "TB_C40_050SC030", label: "TB_C40_050SC030 (연주설비사양)" },
    { id: "TB_C40_050SC040", label: "TB_C40_050SC040 (열연설비사양)" },
    { id: "TB_C40_050SC070", label: "TB_C40_050SC070 (Edging능력기준)" },
    { id: "TB_C40_050SC080", label: "TB_C40_050SC080 (열연Min단중)" },
    { id: "TB_C40_050SC090", label: "TB_C40_050SC090 (열연Max단중)" },
    { id: "TB_C40_050SC290", label: "TB_C40_050SC290 (특정고객사 제한)" },
    { id: "TB_C40_050SC370", label: "TB_C40_050SC370 (인도허용 보정)" },
  ],
  method: [
    { id: "calculatePrimaryWidthRange", label: "calculatePrimaryWidthRange (Step 2)" },
    { id: "calculateTargetWidthFor3Pass", label: "calculateTargetWidthFor3Pass (Step 13)" },
    { id: "calculateSplitCount", label: "calculateSplitCount (Step 7)" },
    { id: "calculateUnitCountAndTargetWeight", label: "calculateUnitCountAndTargetWeight (Step 8)" },
    { id: "calculateSecondaryWeightLower", label: "calculateSecondaryWeightLower (Step 5)" },
  ],
  class: [
    { id: "WidthRangeCalculator", label: "WidthRangeCalculator" },
    { id: "WeightRangeCalculator", label: "WeightRangeCalculator" },
    { id: "SlabDesignService", label: "SlabDesignService" },
  ],
  column: [],
  standard_value: [
    { id: "SC070", label: "SC070 — Edging 능력 기준값" },
    { id: "SC080", label: "SC080 — 열연 Min 단중" },
    { id: "SC290", label: "SC290 — 특정고객사 제한" },
  ],
  order: [
    { id: "01S3047892010", label: "01S3047892010 (FAB 60톤, 정상)" },
    { id: "01S3018688050", label: "01S3018688050 (FHA Target단중 29.3)" },
    { id: "01SA139339010", label: "01SA139339010 (FAB hr=939.5)" },
    { id: "01S9999999990", label: "01S9999999990 (DG320 시나리오)" },
  ],
};

const RISK_COLORS: Record<string, string> = {
  HIGH: "bg-red-100 text-red-800 border-red-300",
  MEDIUM: "bg-amber-100 text-amber-800 border-amber-300",
  LOW: "bg-emerald-100 text-emerald-800 border-emerald-300",
};

export function Agent1ImpactForm() {
  const [changeKind, setChangeKind] = useState<ChangeKind>("data");
  const [targetType, setTargetType] = useState<TargetType>("table");
  const [targetId, setTargetId] = useState("TB_C40_050SC070");
  const [modification, setModification] = useState<ModificationType>("value_change");
  const [newValue, setNewValue] = useState("");
  const [showCypher, setShowCypher] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Agent1Result | null>(null);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!targetId) {
      setError("변경 대상을 선택해주세요");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const req: Agent1Request = {
        change_kind: changeKind,
        target_type: targetType,
        target_id: targetId,
        modification_type: modification,
        new_value: newValue || null,
      };
      const r = await runAgent1(req);
      setResult(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const trace = result?.ontology_trace ?? null;
  const seedSet = new Set(trace?.seed_ids ?? []);

  return (
    <div className="space-y-5">
      <h2 className="text-xl font-semibold text-gray-900">
        📊 Agent 1 — 영향도 파악 (온톨로지 그래프 traversal)
      </h2>
      <div className="rounded border border-blue-200 bg-blue-50 p-3 text-xs text-blue-900">
        🌐 Neo4j 온톨로지 그래프를 따라 변경 영향을 추적합니다. 결과 하단에
        실행된 <b>Cypher 쿼리</b>와 <b>그래프 traversal</b>이 함께 표시됩니다.
      </div>

      <div className="rounded border border-gray-200 bg-white p-5 shadow-sm">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">변경 유형</label>
            <div className="flex gap-3 text-sm">
              <label className="flex items-center gap-1.5">
                <input type="radio" checked={changeKind === "program"} onChange={() => setChangeKind("program")} />
                프로그램(소스) 변경
              </label>
              <label className="flex items-center gap-1.5">
                <input type="radio" checked={changeKind === "data"} onChange={() => setChangeKind("data")} />
                데이터(기준값) 변경
              </label>
            </div>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">대상 종류</label>
            <select
              value={targetType}
              onChange={(e) => {
                const t = e.target.value as TargetType;
                setTargetType(t);
                setTargetId(TARGET_PRESETS[t]?.[0]?.id ?? "");
              }}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
            >
              <option value="table">테이블</option>
              <option value="method">메서드</option>
              <option value="class">클래스</option>
              <option value="standard_value">SC 기준값</option>
              <option value="order">📦 주문 (14 Step 시뮬레이션)</option>
              <option value="column">컬럼</option>
            </select>
          </div>
        </div>
        <div className="mt-4">
          <label className="mb-1 block text-sm font-medium text-gray-700">변경 대상</label>
          <select
            value={targetId}
            onChange={(e) => setTargetId(e.target.value)}
            className="w-full rounded border border-gray-300 px-3 py-2 text-sm font-mono"
          >
            {(TARGET_PRESETS[targetType] ?? []).map((p) => (
              <option key={p.id} value={p.id}>{p.label}</option>
            ))}
          </select>
        </div>
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">변경 종류</label>
            <select
              value={modification}
              onChange={(e) => setModification(e.target.value as ModificationType)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
            >
              <option value="value_change">값 변경</option>
              <option value="logic">로직 변경</option>
              <option value="signature">시그니처 변경</option>
              <option value="deletion">삭제</option>
            </select>
          </div>
          {changeKind === "data" && (
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">새 값 (선택)</label>
              <input
                type="text" value={newValue} onChange={(e) => setNewValue(e.target.value)}
                className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
                placeholder="예: 1500"
              />
            </div>
          )}
        </div>
        <button
          onClick={submit} disabled={loading}
          className="mt-5 rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:opacity-60"
        >
          {loading ? "온톨로지 traversal 실행 중..." : "🔍 영향도 분석 실행"}
        </button>
        {error && (
          <div className="mt-3 rounded border border-red-300 bg-red-50 p-2 text-sm text-red-800">⚠️ {error}</div>
        )}
      </div>

      {result && (
        <div className="space-y-4">
          <div className="rounded border border-gray-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <div className="text-sm text-gray-700">{result.summary}</div>
              {result.risk_level && (
                <span className={`rounded border px-2.5 py-1 text-xs font-semibold ${RISK_COLORS[result.risk_level]}`}>
                  위험도: {result.risk_level}
                </span>
              )}
            </div>
            {result.risk_factors.length > 0 && (
              <div className="mt-2 text-xs text-gray-500">요인: {result.risk_factors.join(" · ")}</div>
            )}
          </div>

          <ResultTable
            caption="🟢 직접 영향 — 메서드"
            columns={[
              { key: "class", header: "Class" },
              { key: "name", header: "Method" },
            ]}
            rows={(result.direct_impact.methods ?? []) as unknown as Record<string, unknown>[]}
            emptyMessage="직접 영향 메서드 없음"
          />
          <ResultTable
            caption="🟢 직접 영향 — Step"
            columns={[
              { key: "step_number", header: "#", width: "60px" },
              { key: "korean_name", header: "Step" },
              { key: "via_standard", header: "경유 SC" },
            ]}
            rows={(result.direct_impact.affected_steps ?? []) as unknown as Record<string, unknown>[]}
            emptyMessage="직접 영향 Step 없음"
          />
          <ResultTable
            caption="🟠 간접 영향 — 다운스트림 Step"
            columns={[
              { key: "step_number", header: "#", width: "60px" },
              { key: "korean_name", header: "Step" },
            ]}
            rows={(result.indirect_impact.downstream_steps ?? []) as unknown as Record<string, unknown>[]}
            emptyMessage="다운스트림 영향 없음"
          />

          {trace && trace.nodes.length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-semibold text-gray-700">
                🌐 온톨로지 그래프 — 변경 대상(빨강) 중심 traversal
              </h3>
              <OntologySubgraphView
                nodes={trace.nodes} edges={trace.edges} highlightIds={seedSet} height={500}
              />
            </div>
          )}

          {trace?.cypher && (
            <div className="rounded border border-gray-200 bg-white">
              <button
                onClick={() => setShowCypher(!showCypher)}
                className="w-full px-3 py-2 text-left text-xs font-semibold text-gray-700 hover:bg-gray-50"
              >
                📜 실행된 Cypher 쿼리 ({showCypher ? "접기" : "펼치기"})
              </button>
              {showCypher && (
                <pre className="overflow-x-auto border-t border-gray-100 bg-slate-900 p-3 text-[11px] text-emerald-300">
                  {trace.cypher}
                </pre>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
