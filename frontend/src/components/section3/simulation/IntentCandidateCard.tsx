"use client";

/** target_selected 게이트 카드 — intent 별 후보 carousel.
 * intent=ambiguous → 의도 명확화 라디오.
 */
import { useState } from "react";
import { Check, X, Ban, ArrowRight } from "lucide-react";

interface Candidate {
  action_id: string;
  label: string;
  score?: number;
  code_method_fqn: string;
  aliases?: string[];
  body_preview?: string;
  location: { file_path: string; line_start: number; line_end: number };
  declared_on_term?: string;
}

interface Props {
  payload: Record<string, unknown>;
  onSelect: (idx: number) => void;
  onRequestOther: () => void;
  onClarify: (intent: string) => void;
  onAbort: () => void;
  busy: boolean;
}

const CLARIFY_OPTIONS = [
  { id: "simulate",   label: "시뮬레이션",  desc: "이 action 을 fixture 로 돌려보고 결과를 본다" },
  { id: "impact",     label: "영향도 분석", desc: "이걸 바꾸면 어디가 영향받는지" },
  { id: "locate",     label: "위치 찾기",   desc: "이 키워드가 어디 박혀있는지" },
  { id: "explain",    label: "설명",        desc: "이게 무엇인지 자연어 답변" },
  { id: "hypothesis", label: "가설 검증",   desc: "가상 시나리오 — 'X 가 새로 추가되면'" },
];

export function IntentCandidateCard({
  payload, onSelect, onRequestOther, onClarify, onAbort, busy,
}: Props) {
  const intent = payload.intent as string;
  const candidates = (payload.candidates as Candidate[] | undefined) ?? [];
  const recommendedIdx = payload.recommended_index as number | null | undefined;
  const userQuery = payload.user_query as string | undefined;
  const [pickedIntent, setPickedIntent] = useState<string | null>(null);

  if (intent === "ambiguous" || candidates.length === 0) {
    return (
      <div className="border border-gray-300 rounded-lg bg-white p-4 space-y-3">
        <header className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-900">의도 명확화 (1/3)</h3>
          <span className="text-xs text-gray-400">intent={intent ?? "?"}</span>
        </header>
        <p className="text-sm text-gray-700">
          "{userQuery}" 의 의도가 명확하지 않습니다. 5종 중 하나를 골라 주세요.
        </p>
        <div className="space-y-1.5">
          {CLARIFY_OPTIONS.map((o) => (
            <label
              key={o.id}
              className={"flex items-start gap-2 p-2 rounded border cursor-pointer " +
                (pickedIntent === o.id
                  ? "border-emerald-500 bg-emerald-50"
                  : "border-gray-200 hover:bg-gray-50")}
            >
              <input
                type="radio"
                checked={pickedIntent === o.id}
                onChange={() => setPickedIntent(o.id)}
                className="mt-1 accent-emerald-500"
              />
              <div className="text-xs">
                <div className="font-semibold text-gray-900">{o.label}</div>
                <div className="text-gray-500">{o.desc}</div>
              </div>
            </label>
          ))}
        </div>
        <div className="flex items-center justify-end gap-2 pt-2 border-t border-gray-200">
          <button onClick={onAbort} disabled={busy} className="px-3 py-1.5 text-xs rounded border border-gray-300 hover:bg-gray-50">
            <Ban size={11} className="inline mr-1" /> 중단
          </button>
          <button
            onClick={() => pickedIntent && onClarify(pickedIntent)}
            disabled={busy || !pickedIntent}
            className="px-3 py-1.5 text-xs rounded bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-50"
          >
            <Check size={11} className="inline mr-1" /> 이 의도로 재검색
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="border border-gray-300 rounded-lg bg-white p-4 space-y-3">
      <header className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-900">대상 후보 선택 (1/3)</h3>
        <span className="text-xs text-gray-400">{candidates.length}건 · intent={intent}</span>
      </header>
      <p className="text-sm text-gray-700 truncate" title={userQuery}>
        "{userQuery}" → 후보 carousel
      </p>
      <ul className="space-y-2 max-h-[420px] overflow-y-auto">
        {candidates.map((c, i) => (
          <li
            key={c.action_id}
            className={
              "p-3 rounded border cursor-pointer transition " +
              (i === recommendedIdx
                ? "border-emerald-500 bg-emerald-50/40 hover:bg-emerald-50"
                : "border-gray-200 bg-white hover:border-gray-300")
            }
            onClick={() => !busy && onSelect(i)}
          >
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm font-semibold text-gray-900">{c.label}</span>
              {i === recommendedIdx && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 border border-emerald-300">
                  추천
                </span>
              )}
              {typeof c.score === "number" && (
                <span className="text-[10px] text-gray-400 ml-auto">score {c.score.toFixed(1)}</span>
              )}
            </div>
            <div className="text-[11px] text-gray-400 mt-1 font-mono truncate" title={c.code_method_fqn}>
              {c.code_method_fqn}
            </div>
            {c.body_preview && (
              <pre className="mt-2 text-[10px] bg-gray-50 border border-gray-200 rounded p-2 overflow-x-auto text-gray-700 max-h-32">
                {c.body_preview.slice(0, 400)}
              </pre>
            )}
            <div className="mt-2 flex items-center justify-end">
              <span className="text-[10px] text-emerald-700 inline-flex items-center gap-1">
                선택 <ArrowRight size={11} />
              </span>
            </div>
          </li>
        ))}
      </ul>
      <div className="flex items-center justify-end gap-2 pt-2 border-t border-gray-200">
        <button onClick={onAbort} disabled={busy} className="px-3 py-1.5 text-xs rounded border border-gray-300 hover:bg-gray-50">
          <Ban size={11} className="inline mr-1" /> 중단
        </button>
        <button onClick={onRequestOther} disabled={busy} className="px-3 py-1.5 text-xs rounded border border-gray-300 hover:bg-gray-50">
          <X size={11} className="inline mr-1" /> 다른 후보
        </button>
      </div>
    </div>
  );
}
