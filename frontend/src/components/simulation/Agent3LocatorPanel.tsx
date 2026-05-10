"use client";

import { useState } from "react";
import { runAgent3, type Agent3Result } from "@/lib/simulation/agentApi";

interface Props {
  /** 핸드오프: 사용자가 "이 step 시뮬" 버튼 클릭 시 부모(AgentHub)에게 알림. */
  onHandoffToTest?: (stepId: string) => void;
}

const QUICK_QUERIES = [
  "단중상한이 어디서 결정돼?",
  "누적 실수율 계산 위치",
  "Slab 매수 산정 로직",
  "분할수 범위 계산",
  "Slab 두께 결정",
  "PRODUCT_TYPE_CD 사용처",
  "주문 정합성 검증 (DG001~005)",
];

/**
 * Agent 3 패널 — 비즈니스 용어 → 소스/테이블/프로세스 위치 + 코드 미리보기 + A2 핸드오프.
 *
 * 시연 시나리오 1: "단중상한"으로 검색 → 4개 컬럼 + 2개 step + Monaco preview + 즉시 시뮬.
 */
export function Agent3LocatorPanel({ onHandoffToTest }: Props) {
  const [query, setQuery] = useState("단중상한이 어디서 결정돼?");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Agent3Result | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeIdx, setActiveIdx] = useState(0);

  const submit = async (q?: string) => {
    const text = (q ?? query).trim();
    if (!text) return;
    if (q) setQuery(q);
    setLoading(true);
    setError(null);
    setResult(null);
    setActiveIdx(0);
    try {
      const r = await runAgent3({
        natural_language_query: text,
        include_preview: true,
        preview_lines: 20,
      });
      setResult(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const activeLocation = result?.source_locations?.[activeIdx];

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[420px_1fr]">
      {/* 입력 패널 */}
      <section className="rounded-lg border border-gray-200 bg-white p-4 space-y-4">
        <h2 className="text-base font-semibold text-gray-800">위치 파악</h2>
        <p className="text-xs text-gray-500">
          비즈니스 용어를 자연어로 입력하면 ontology + slab-design 키워드 매핑으로
          소스 코드 위치를 찾고 미리보기를 제공합니다.
        </p>

        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">검색어 (자연어)</label>
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            rows={3}
            className="w-full rounded border border-gray-300 px-3 py-2 text-sm font-mono"
            placeholder="예: 단중상한이 어디서 결정돼?"
          />
        </div>

        {/* 빠른 질의 버튼 */}
        <div>
          <div className="text-xs font-medium text-gray-700 mb-1">빠른 질의</div>
          <div className="flex flex-wrap gap-1">
            {QUICK_QUERIES.map((q) => (
              <button
                key={q}
                onClick={() => submit(q)}
                className="rounded border border-gray-300 bg-gray-50 px-2 py-1 text-xs text-gray-700 hover:bg-gray-100"
              >
                {q}
              </button>
            ))}
          </div>
        </div>

        <button
          disabled={loading}
          onClick={() => submit()}
          className="w-full rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:bg-gray-300"
        >
          {loading ? "검색 중..." : "🔍 위치 검색"}
        </button>

        {error && (
          <div className="rounded bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-700">
            {error}
          </div>
        )}

        {/* 매칭된 키워드 */}
        {result && result.extracted_keywords?.length > 0 && (
          <div>
            <div className="text-xs font-medium text-gray-700 mb-1">매칭 키워드</div>
            <div className="flex flex-wrap gap-1">
              {result.extracted_keywords.map((k, i) => (
                <span key={i} className="rounded bg-blue-100 text-blue-800 px-2 py-0.5 text-xs">
                  {k}
                </span>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* 결과 패널 */}
      <section className="space-y-4">
        {!result && !loading && (
          <div className="rounded-lg border border-dashed border-gray-300 p-8 text-center text-sm text-gray-400">
            검색어를 입력하면 매칭된 코드 위치 + 미리보기 + 시뮬레이션 핸드오프가 표시됩니다.
          </div>
        )}

        {result && result.source_locations.length === 0 && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-6 text-center text-sm text-amber-800">
            매칭된 위치가 없습니다. 다른 키워드를 시도해보세요.
          </div>
        )}

        {result && result.source_locations.length > 0 && (
          <>
            {/* 요약 + 핸드오프 */}
            <div className="rounded-lg border border-gray-200 bg-white p-4 flex items-center justify-between">
              <div>
                <div className="text-sm font-semibold text-gray-800">{result.summary}</div>
                <div className="text-xs text-gray-500 mt-1">
                  {result.source_locations.length}개 위치 ·
                  {result.matched_terms.length > 0 ? ` ${result.matched_terms.length}개 용어 매칭 ·` : ""}
                  추출방식: {result.extraction_method}
                </div>
              </div>
              {result.handoff_step_id && onHandoffToTest && (
                <button
                  onClick={() => onHandoffToTest(result.handoff_step_id!)}
                  className="rounded bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-700"
                  title={`Agent 2 패널로 이동하여 step "${result.handoff_step_id}" 실행`}
                >
                  ⚡ 이 step 시뮬레이션 →
                </button>
              )}
            </div>

            {/* 위치 탭 + Monaco preview */}
            <div className="rounded-lg border border-gray-200 bg-white">
              <div className="border-b border-gray-200 px-3 py-1 flex flex-wrap gap-1 bg-gray-50">
                {result.source_locations.map((loc, idx) => (
                  <button
                    key={idx}
                    onClick={() => setActiveIdx(idx)}
                    className={`rounded px-2 py-1 text-xs font-mono transition-colors ${
                      idx === activeIdx
                        ? "bg-white border border-gray-300 text-gray-800"
                        : "text-gray-500 hover:text-gray-800"
                    }`}
                  >
                    {loc.class_name ?? "(unknown)"}
                    {loc.method_name && <span className="text-gray-400">.{loc.method_name}</span>}
                  </button>
                ))}
              </div>
              {activeLocation && (
                <div className="p-4">
                  <div className="text-xs text-gray-500 mb-2 font-mono">
                    {activeLocation.file_path?.replace(/^.*\/sample-repos\//, "sample-repos/")}
                    {activeLocation.line && <span> : line {activeLocation.line}</span>}
                  </div>
                  {activeLocation.preview ? (
                    <pre className="rounded bg-gray-900 text-gray-100 px-3 py-2 text-xs overflow-x-auto leading-relaxed">
                      <code>{activeLocation.preview}</code>
                    </pre>
                  ) : (
                    <div className="text-sm text-gray-400">미리보기 없음</div>
                  )}
                  {activeLocation.step_id && (
                    <div className="mt-3 flex items-center gap-2 text-xs text-gray-600">
                      <span>관련 sandbox step:</span>
                      <code className="rounded bg-purple-100 text-purple-800 px-2 py-0.5">
                        {activeLocation.step_id}
                      </code>
                      {onHandoffToTest && (
                        <button
                          onClick={() => onHandoffToTest(activeLocation.step_id!)}
                          className="text-purple-600 hover:underline"
                        >
                          이 step으로 시뮬 →
                        </button>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </>
        )}
      </section>
    </div>
  );
}
