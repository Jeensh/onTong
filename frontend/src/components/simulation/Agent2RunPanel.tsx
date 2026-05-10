"use client";

import { useEffect, useState } from "react";
import { useAgent2Stream, type CaseType } from "@/lib/simulation/useAgent2Stream";
import { SandboxConsole } from "./SandboxConsole";
import { ResultChart } from "./ResultChart";

interface Props {
  /** Agent 3 핸드오프로 전달된 step_id (있으면 자동 설정). */
  initialStepId?: string;
  /** initialStepId를 소비했음을 부모에게 알리는 콜백. */
  onConsumeInitial?: () => void;
}

const STEP_OPTIONS = [
  { id: "pipeline", label: "End-to-end 파이프라인 (검증 → 실수율 → step 8/9/10)" },
  { id: "validator", label: "Validator (DG001~005)" },
  { id: "productivity", label: "누적 실수율" },
  { id: "thickness", label: "Step 1 — Slab 두께" },
  { id: "split_range", label: "Step 8 — 분할수 고려 단중 범위" },
  { id: "slab_count", label: "Step 9 — Slab 매수 ★" },
  { id: "slab_weight", label: "Step 10 — Slab 단중 + 설계대기량 만족" },
];

const CASE_TYPES: { id: CaseType; label: string; color: string; desc: string }[] = [
  { id: "normal", label: "정상", color: "bg-emerald-100 text-emerald-800", desc: "통과 기대 분포" },
  { id: "boundary", label: "경계값", color: "bg-amber-100 text-amber-800", desc: "임계치/0/매우 작은 값" },
  { id: "error", label: "오류", color: "bg-red-100 text-red-800", desc: "DG001~005 trigger" },
  { id: "performance", label: "성능", color: "bg-purple-100 text-purple-800", desc: "대량 Slab 케이스" },
];

/**
 * Agent 2 메인 패널 — Section 3의 핵심 데모.
 *
 * 사용자 흐름:
 * 1. step 선택
 * 2. case_type 다중 선택
 * 3. count 입력
 * 4. (옵션) rules 변경 (시나리오 5: HRF 0.93→0.85)
 * 5. 실행 → 실시간 sandbox 콘솔 + Plotly 차트 + 코드 스켈레톤 다운로드
 */
export function Agent2RunPanel({ initialStepId, onConsumeInitial }: Props = {}) {
  const [stepId, setStepId] = useState(initialStepId ?? "pipeline");
  const [selectedCases, setSelectedCases] = useState<CaseType[]>(["normal", "boundary"]);
  const [count, setCount] = useState(20);
  const [hrfRule, setHrfRule] = useState("");
  const [hrRule, setHrRule] = useState("");

  const stream = useAgent2Stream();

  // Agent 3 핸드오프: 새 step_id가 도착하면 한 번만 적용
  useEffect(() => {
    if (initialStepId) {
      setStepId(initialStepId);
      onConsumeInitial?.();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialStepId]);

  const toggleCase = (c: CaseType) => {
    setSelectedCases((prev) => (prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]));
  };

  const submit = async () => {
    if (selectedCases.length === 0) return;
    const rules: Record<string, string> = {};
    if (hrRule.trim()) rules.hr = hrRule.trim();
    if (hrfRule.trim()) rules.hrf = hrfRule.trim();
    await stream.start({
      target_id: stepId,
      case_types: selectedCases,
      test_count: count,
      rules: Object.keys(rules).length > 0 ? rules : undefined,
    });
  };

  const downloadSkeleton = () => {
    if (!stream.summary?.code_skeleton) return;
    const blob = new Blob([stream.summary.code_skeleton], { type: "text/x-python" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `test_${stepId}_${Date.now()}.py`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[420px_1fr]">
      {/* 입력 패널 */}
      <section className="rounded-lg border border-gray-200 bg-white p-4 space-y-4">
        <h2 className="text-base font-semibold text-gray-800">테스트 데이터 자동 생성</h2>
        <p className="text-xs text-gray-500">
          slab-design 알고리즘 step에 대해 Hypothesis 기반으로 케이스를 자동 생성하고
          격리된 Python 샌드박스에서 실행합니다.
        </p>

        {/* Step */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">대상 Step</label>
          <select
            value={stepId}
            onChange={(e) => setStepId(e.target.value)}
            className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
          >
            {STEP_OPTIONS.map((s) => (
              <option key={s.id} value={s.id}>{s.label}</option>
            ))}
          </select>
        </div>

        {/* Case types */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">케이스 유형</label>
          <div className="space-y-1">
            {CASE_TYPES.map((c) => (
              <label key={c.id} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={selectedCases.includes(c.id)}
                  onChange={() => toggleCase(c.id)}
                />
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${c.color}`}>
                  {c.label}
                </span>
                <span className="text-xs text-gray-500">{c.desc}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Count */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            유형별 케이스 수: <span className="text-blue-600">{count}</span>
          </label>
          <input
            type="range"
            min={1}
            max={100}
            value={count}
            onChange={(e) => setCount(Number(e.target.value))}
            className="w-full"
          />
          <div className="text-[10px] text-gray-400">
            총 {count * selectedCases.length}건 생성 (각 유형마다 {count}건)
          </div>
        </div>

        {/* Rules (optional) — 시나리오 5 데모용 */}
        <details className="text-sm">
          <summary className="cursor-pointer text-gray-700 font-medium">
            ⚙️ 룰 변경 (시나리오 5)
          </summary>
          <div className="mt-2 space-y-2 pl-4 border-l-2 border-gray-200">
            <p className="text-[11px] text-gray-500">
              pipeline step에서 누적 실수율 곱 변동을 시뮬. 빈 값 → default 사용.
            </p>
            <div>
              <label className="block text-xs text-gray-600">HR 실수율 (default 0.95)</label>
              <input
                type="text"
                value={hrRule}
                onChange={(e) => setHrRule(e.target.value)}
                placeholder="0.92"
                className="w-full rounded border border-gray-300 px-2 py-1 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-600">HRF 실수율 (default 0.93)</label>
              <input
                type="text"
                value={hrfRule}
                onChange={(e) => setHrfRule(e.target.value)}
                placeholder="0.85"
                className="w-full rounded border border-gray-300 px-2 py-1 text-sm"
              />
            </div>
          </div>
        </details>

        {/* 실행 / 취소 */}
        <div className="flex gap-2">
          <button
            disabled={stream.running || selectedCases.length === 0}
            onClick={submit}
            className="flex-1 rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:bg-gray-300"
          >
            {stream.running ? "실행 중..." : "▶ 실행"}
          </button>
          {stream.running && (
            <button
              onClick={stream.cancel}
              className="rounded border border-red-300 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50"
            >
              취소
            </button>
          )}
        </div>

        {/* 코드 스켈레톤 다운로드 */}
        {stream.summary && (
          <button
            onClick={downloadSkeleton}
            className="w-full rounded border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            📥 pytest 스켈레톤 다운로드
          </button>
        )}

        {stream.error && (
          <div className="rounded bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-700">
            {stream.error}
          </div>
        )}
      </section>

      {/* 결과 패널 */}
      <section className="space-y-4">
        <div className="h-72">
          <SandboxConsole
            cases={stream.cases}
            progress={stream.progress}
            running={stream.running}
          />
        </div>

        <ResultChart summary={stream.summary} />

        {/* 실패 케이스 상세 */}
        {stream.failures.length > 0 && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4">
            <h4 className="text-sm font-semibold text-red-800 mb-2">
              기대 불일치 케이스 ({stream.failures.length}건)
            </h4>
            <div className="max-h-64 overflow-y-auto space-y-2">
              {stream.failures.slice(0, 20).map((f) => (
                <div key={f.case_id} className="rounded border border-red-200 bg-white p-2 text-xs">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-mono text-red-700">{f.case_id}</span>
                    <span className="text-gray-500">{f.description}</span>
                  </div>
                  <div className="text-gray-600">
                    expected: <code className="bg-gray-100 px-1">{JSON.stringify(f.expected)}</code>
                  </div>
                  <div className="text-gray-600">
                    actual: <code className="bg-gray-100 px-1 truncate inline-block max-w-full">
                      {JSON.stringify(f.actual_output).slice(0, 200)}
                    </code>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
