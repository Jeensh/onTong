"use client";

import { useMemo, useState } from "react";
import {
  runAgent2,
  type Agent2Result,
  type CaseType,
} from "@/lib/simulation/agentApi";
import { OntologySubgraphView } from "./shared/OntologySubgraphView";
import { ResultTable } from "./shared/ResultTable";

const STEP_OPTIONS = [
  { id: "step_1", label: "Step 1 — 두께 계산" },
  { id: "step_2", label: "Step 2 — 1차 폭범위 계산" },
  { id: "step_3", label: "Step 3 — 1차 길이범위 계산" },
  { id: "step_4", label: "Step 4 — 1차 단중범위 계산" },
  { id: "step_5", label: "Step 5 — 2차 단중하한 계산" },
  { id: "step_6", label: "Step 6 — 2차 단중상한 계산" },
  { id: "step_7", label: "Step 7 — 분할수 계산" },
  { id: "step_8", label: "Step 8 — 매수 및 Target 단중" },
  { id: "step_10", label: "Step 10 — 2차 폭범위 계산" },
  { id: "step_12", label: "Step 12 — Target 폭 계산" },
  { id: "step_13", label: "Step 13 — Target 폭 재계산 (3pass)" },
  { id: "step_14", label: "Step 14 — Target 길이 계산" },
];

const CASE_TYPES: { id: CaseType; label: string; color: string }[] = [
  { id: "normal", label: "정상", color: "bg-emerald-100 text-emerald-800" },
  { id: "boundary", label: "경계값", color: "bg-amber-100 text-amber-800" },
  { id: "error", label: "에러", color: "bg-red-100 text-red-800" },
  { id: "performance", label: "성능", color: "bg-purple-100 text-purple-800" },
];

export function Agent2TestDataForm() {
  const [stepId, setStepId] = useState<string>("step_2");
  const [selectedCases, setSelectedCases] = useState<CaseType[]>([
    "normal", "boundary", "error",
  ]);
  const [count, setCount] = useState(5);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Agent2Result | null>(null);
  const [error, setError] = useState<string | null>(null);

  const toggleCase = (c: CaseType) => {
    setSelectedCases((prev) =>
      prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]
    );
  };

  const submit = async () => {
    if (selectedCases.length === 0) {
      setError("케이스 유형을 1개 이상 선택해주세요");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const r = await runAgent2({
        target_type: "step",
        target_id: stepId,
        case_types: selectedCases,
        test_count: count,
      });
      setResult(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const tableRows = useMemo(
    () =>
      (result?.test_cases ?? []).map((tc) => ({
        case_id: tc.case_id,
        case_type: tc.case_type,
        description: tc.description,
        input: JSON.stringify(tc.input_data),
        expected: JSON.stringify(tc.expected_output),
      })),
    [result]
  );

  const trace = result?.ontology_trace ?? null;
  const seedSet = new Set(trace?.seed_ids ?? []);

  return (
    <div className="space-y-5">
      <h2 className="text-xl font-semibold text-gray-900">
        🧪 Agent 2 — 테스트 데이터 (변수 의존성 그래프)
      </h2>

      <div className="rounded border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-900">
        🌐 Step의 <code>REQUIRES_INPUT</code> / <code>PRODUCES_OUTPUT</code> /
        <code>USES_STANDARD</code> / <code>TRIGGERS_ON_FAIL</code> 관계를 추적해
        입력 변수의 valid_range 기반으로 정상/경계/에러 케이스를 생성합니다.
      </div>

      <div className="rounded border border-gray-200 bg-white p-5 shadow-sm">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">테스트 대상 Step</label>
            <select
              value={stepId} onChange={(e) => setStepId(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
            >
              {STEP_OPTIONS.map((s) => (
                <option key={s.id} value={s.id}>{s.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">생성 개수</label>
            <input
              type="number" min={1} max={20} value={count}
              onChange={(e) => setCount(parseInt(e.target.value || "5", 10))}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
        </div>
        <div className="mt-4">
          <label className="mb-1 block text-sm font-medium text-gray-700">케이스 유형</label>
          <div className="flex flex-wrap gap-2">
            {CASE_TYPES.map((c) => (
              <label
                key={c.id}
                className={`cursor-pointer rounded border px-2.5 py-1 text-xs font-medium ${
                  selectedCases.includes(c.id)
                    ? `${c.color} border-current`
                    : "border-gray-300 bg-gray-50 text-gray-500"
                }`}
              >
                <input
                  type="checkbox" className="mr-1"
                  checked={selectedCases.includes(c.id)}
                  onChange={() => toggleCase(c.id)}
                />
                {c.label}
              </label>
            ))}
          </div>
        </div>
        <button
          onClick={submit} disabled={loading}
          className="mt-5 rounded bg-emerald-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-emerald-700 disabled:opacity-60"
        >
          {loading ? "생성 중..." : "🧪 테스트 데이터 생성"}
        </button>
        {error && (
          <div className="mt-3 rounded border border-red-300 bg-red-50 p-2 text-sm text-red-800">⚠️ {error}</div>
        )}
      </div>

      {result && (
        <div className="space-y-4">
          <div className="rounded border border-gray-200 bg-white p-4 shadow-sm text-sm text-gray-700">
            {result.summary}
          </div>

          <ResultTable
            caption="📋 생성된 테스트 케이스"
            columns={[
              { key: "case_id", header: "ID", width: "80px" },
              { key: "case_type", header: "유형", width: "80px" },
              { key: "description", header: "설명" },
              { key: "input", header: "입력" },
              { key: "expected", header: "기대" },
            ]}
            rows={tableRows}
          />

          {result.data_dependencies.length > 0 && (
            <div className="rounded border border-gray-200 bg-white p-3 text-sm">
              <div className="mb-1 text-xs font-semibold uppercase text-gray-500">
                💾 데이터 의존성 (테이블)
              </div>
              <div className="flex flex-wrap gap-1.5">
                {result.data_dependencies.map((t) => (
                  <span key={t} className="rounded bg-gray-100 px-2 py-0.5 font-mono text-xs">{t}</span>
                ))}
              </div>
            </div>
          )}

          {trace && trace.nodes.length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-semibold text-gray-700">
                🌐 Step 의존성 그래프 — Variable / Standard / ErrorCode 추적
              </h3>
              <OntologySubgraphView
                nodes={trace.nodes} edges={trace.edges}
                highlightIds={seedSet} height={420}
              />
            </div>
          )}

          {result.code_skeleton && (
            <details className="rounded border border-gray-200 bg-white">
              <summary className="cursor-pointer px-4 py-2 text-sm font-medium text-gray-700">
                🧱 JUnit 코드 스켈레톤 (펼치기)
              </summary>
              <pre className="overflow-x-auto border-t border-gray-100 bg-gray-50 p-3 text-xs">
                {result.code_skeleton}
              </pre>
            </details>
          )}
        </div>
      )}
    </div>
  );
}
