"use client";

import { useState } from "react";
import {
  runAgent3,
  type Agent3Result,
  type LocatorScope,
} from "@/lib/simulation/agentApi";
import { OntologySubgraphView } from "./shared/OntologySubgraphView";
import { ResultTable } from "./shared/ResultTable";

const SCOPES: { id: LocatorScope; label: string }[] = [
  { id: "process", label: "프로세스 (Step)" },
  { id: "source", label: "소스 (Class/Method)" },
  { id: "table", label: "테이블" },
];

const METHOD_BADGES: Record<string, { color: string; label: string }> = {
  llm: { color: "border-purple-300 bg-purple-100 text-purple-800", label: "🤖 LLM (Gemini)" },
  explicit: { color: "border-blue-300 bg-blue-100 text-blue-800", label: "📝 명시 키워드" },
  split: { color: "border-gray-300 bg-gray-100 text-gray-700", label: "🔧 단순 토큰화" },
  none: { color: "border-amber-300 bg-amber-100 text-amber-800", label: "ℹ️ 없음" },
};

export function Agent3LocatorForm() {
  const [query, setQuery] = useState("Edging 로직 어디 있어?");
  const [scopes, setScopes] = useState<LocatorScope[]>([
    "process", "source", "table",
  ]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Agent3Result | null>(null);
  const [error, setError] = useState<string | null>(null);

  const toggleScope = (s: LocatorScope) => {
    setScopes((prev) => (prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]));
  };

  const submit = async () => {
    if (!query.trim()) {
      setError("질문/키워드를 입력해주세요");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const r = await runAgent3({
        natural_language_query: query,
        search_scope: scopes.length ? scopes : ["process", "source", "table"],
      });
      setResult(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const trace = result?.ontology_trace ?? null;
  const seedSet = new Set(trace?.seed_ids ?? []);
  const pathKeys = new Set(trace?.path_edge_keys ?? []);

  return (
    <div className="space-y-5">
      <h2 className="text-xl font-semibold text-gray-900">
        🗺 Agent 3 — 비즈니스 용어 위치 파악 (그래프 path highlight)
      </h2>

      <div className="rounded border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
        🌐 자연어 → 키워드 추출 (LLM/split) → Term 매칭 → REFERS_TO_PROCESS →
        Step → CALCULATES → Method 경로를 그래프로 highlight 합니다.
      </div>

      <div className="rounded border border-gray-200 bg-white p-5 shadow-sm">
        <label className="mb-1 block text-sm font-medium text-gray-700">
          찾고 싶은 업무 용어 / 자연어 질문
        </label>
        <input
          type="text" value={query} onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
          placeholder='예: "Edging 기준 어디서 체크해?"'
        />
        <div className="mt-4">
          <label className="mb-1 block text-sm font-medium text-gray-700">검색 범위</label>
          <div className="flex flex-wrap gap-2 text-xs">
            {SCOPES.map((s) => (
              <label key={s.id} className={`cursor-pointer rounded border px-2.5 py-1 font-medium ${
                scopes.includes(s.id)
                  ? "border-amber-300 bg-amber-100 text-amber-800"
                  : "border-gray-300 bg-gray-50 text-gray-500"
              }`}>
                <input type="checkbox" className="mr-1"
                       checked={scopes.includes(s.id)} onChange={() => toggleScope(s.id)} />
                {s.label}
              </label>
            ))}
          </div>
        </div>
        <button
          onClick={submit} disabled={loading}
          className="mt-5 rounded bg-amber-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-amber-700 disabled:opacity-60"
        >
          {loading ? "검색 중..." : "🔍 위치 파악 실행"}
        </button>
        {error && (
          <div className="mt-3 rounded border border-red-300 bg-red-50 p-2 text-sm text-red-800">⚠️ {error}</div>
        )}
      </div>

      {result && (
        <div className="space-y-4">
          <div className="rounded border border-gray-200 bg-white p-4 shadow-sm">
            <div className="text-sm text-gray-700">{result.summary}</div>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
              <span className="text-gray-500">키워드 추출:</span>
              <span className={`rounded border px-2 py-0.5 font-semibold ${METHOD_BADGES[result.extraction_method]?.color}`}>
                {METHOD_BADGES[result.extraction_method]?.label}
              </span>
              {result.extracted_keywords.length > 0 && (
                <span className="flex flex-wrap items-center gap-1 text-gray-500">
                  →
                  {result.extracted_keywords.map((k) => (
                    <span key={k} className="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-gray-700">{k}</span>
                  ))}
                </span>
              )}
            </div>
          </div>

          <ResultTable
            caption="🔍 매칭된 업무 용어"
            columns={[
              { key: "korean", header: "한글" },
              { key: "english", header: "English" },
              { key: "category", header: "분류" },
              { key: "description", header: "설명" },
            ]}
            rows={result.matched_terms as unknown as Record<string, unknown>[]}
            emptyMessage="매칭된 용어 없음"
          />

          {scopes.includes("process") && (
            <ResultTable
              caption="🟢 관련 프로세스 (Step)"
              columns={[
                { key: "step_number", header: "#", width: "60px" },
                { key: "korean_name", header: "Step" },
                {
                  key: "roles", header: "역할",
                  render: (v) => (Array.isArray(v) ? (v as string[]).join(", ") : ""),
                },
              ]}
              rows={result.process_locations as unknown as Record<string, unknown>[]}
              emptyMessage="관련 Step 없음"
            />
          )}

          {scopes.includes("source") && (
            <ResultTable
              caption="🟠 관련 소스 (Class.Method)"
              columns={[
                { key: "step_number", header: "Step", width: "70px" },
                { key: "class_name", header: "Class" },
                { key: "method_name", header: "Method" },
              ]}
              rows={result.source_locations as unknown as Record<string, unknown>[]}
              emptyMessage="관련 소스 없음"
            />
          )}

          {scopes.includes("table") && (
            <ResultTable
              caption="💾 관련 테이블"
              columns={[
                { key: "table_name", header: "Table" },
                { key: "standard_code", header: "SC 코드" },
              ]}
              rows={result.data_locations as unknown as Record<string, unknown>[]}
              emptyMessage="관련 테이블 없음"
            />
          )}

          {trace && trace.nodes.length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-semibold text-gray-700">
                🌐 검색 path highlight — Term → Step → Method 경로 (보라색 진하게)
              </h3>
              <OntologySubgraphView
                nodes={trace.nodes} edges={trace.edges}
                highlightIds={seedSet} pathEdgeKeys={pathKeys}
                height={460}
              />
            </div>
          )}

          {result.related_terms.length > 0 && (
            <ResultTable
              caption="🔗 연관 용어"
              columns={[
                { key: "korean", header: "한글" },
                { key: "english", header: "English" },
                { key: "relation", header: "관계" },
              ]}
              rows={result.related_terms as unknown as Record<string, unknown>[]}
            />
          )}
        </div>
      )}
    </div>
  );
}
