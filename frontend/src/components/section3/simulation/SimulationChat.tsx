"use client";

/**
 * 시뮬레이션 에이전트 — chat shell (Phase B scaffold).
 *
 * 3-pane (좌 chat · 중 active gate · 우 graph+7-tab) 의 외곽만 + /start /respond
 * /replay 흐름 wire. intent 별 차별 layout 은 Phase F 에서.
 */
import { useEffect, useState } from "react";
import { Workflow, Send, RotateCcw } from "lucide-react";
import { simulationApi, type ReplayResponse, type SimulationGate } from "@/lib/section3/simulation";

interface Props {
  initialSid: string | null;
  onNewSession: () => void;
  defaultRepoId: string | null;
}

const PRESET_QUESTIONS: { intent: string; label: string; query: string }[] = [
  { intent: "impact",     label: "① 기능 개선 영향",  query: "단중 계산 로직 바꾸면 어디 영향?" },
  { intent: "impact",     label: "② 기준 변경 영향",  query: "design 정책 standard 0.5 → 0.3 으로 바꾸면?" },
  { intent: "simulate",   label: "③ 주문 변경 비교",  query: "이 주문의 thickness 만 바꿔 돌려봐" },
  { intent: "locate",     label: "④ 코드 위치 찾기",  query: "edging 룰은 어디 박혀있어?" },
  { intent: "hypothesis", label: "⑤ 신규 품종 추가",  query: "신규 품종 HC600X 추가되면 어떤 영향?" },
];

export function SimulationChat({ initialSid, onNewSession, defaultRepoId }: Props) {
  const [sid, setSid] = useState<string | null>(initialSid);
  const [repo] = useState<string>(defaultRepoId ?? "slab-design-real-v2");
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastGate, setLastGate] = useState<SimulationGate | null>(null);
  const [lastMessage, setLastMessage] = useState<string>("");
  const [replay, setReplay] = useState<ReplayResponse | null>(null);

  // initialSid 있으면 replay 가져오기
  useEffect(() => {
    if (!initialSid) return;
    simulationApi.replay(initialSid).then(setReplay).catch((e) => {
      setError(`replay 실패: ${String(e)}`);
    });
  }, [initialSid]);

  async function _onStart() {
    if (!query.trim() || busy) return;
    setBusy(true); setError(null);
    try {
      const r = await simulationApi.start({ user_query: query, repo_id: repo });
      setSid(r.session_id);
      setLastGate(r.next_gate);
      setLastMessage(r.message);
      const fresh = await simulationApi.replay(r.session_id);
      setReplay(fresh);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function _onReset() {
    setSid(null); setReplay(null); setLastGate(null); setLastMessage("");
    setQuery(""); setError(null);
    onNewSession();
  }

  return (
    <div className="h-full grid" style={{ gridTemplateColumns: "33% 1px 40% 1px 27%" }}>
      {/* ─────────── 좌측 chat ─────────── */}
      <div className="flex flex-col h-full overflow-hidden bg-white">
        <div className="px-4 py-3 border-b border-gray-200 flex items-center gap-2">
          <Workflow size={16} className="text-emerald-600" />
          <strong className="text-sm">시뮬레이션 에이전트</strong>
          <span className="text-xs text-gray-400 ml-auto">{repo}</span>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {!sid && (
            <div className="text-sm text-gray-500 leading-relaxed">
              자연어로 질문해 주세요. 5 시나리오 예시:
              <ul className="mt-2 space-y-1.5">
                {PRESET_QUESTIONS.map((q) => (
                  <li key={q.query}>
                    <button
                      onClick={() => setQuery(q.query)}
                      className="text-left text-xs px-2 py-1.5 rounded border border-gray-200 hover:border-emerald-500 hover:bg-emerald-50 w-full"
                    >
                      <span className="text-gray-400 mr-1.5">{q.label}</span>
                      <span className="text-gray-800">{q.query}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {replay?.decisions.map((d) => (
            <div key={d.turn_no} className="text-xs">
              <div className="text-gray-400 mb-1">turn {d.turn_no} · {d.gate_kind}</div>
              <pre className="bg-gray-50 border border-gray-200 rounded p-2 text-[11px] overflow-x-auto">
                {JSON.stringify(d.payload, null, 2).slice(0, 800)}
              </pre>
            </div>
          ))}

          {lastMessage && (
            <div className="text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 rounded p-2">
              {lastMessage}
            </div>
          )}

          {error && (
            <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2">
              {error}
            </div>
          )}
        </div>

        <div className="p-3 border-t border-gray-200">
          <div className="flex items-end gap-2">
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); _onStart(); }
              }}
              placeholder="질문을 입력하세요 (Enter 전송, Shift+Enter 줄바꿈)..."
              rows={2}
              disabled={busy || !!sid}
              className="flex-1 text-sm bg-white border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-1 focus:ring-emerald-500 resize-none disabled:bg-gray-50"
            />
            {sid ? (
              <button
                onClick={_onReset}
                className="p-2 rounded border border-gray-300 hover:bg-gray-50"
                title="새 세션"
              >
                <RotateCcw size={16} />
              </button>
            ) : (
              <button
                onClick={_onStart}
                disabled={busy || !query.trim()}
                className="p-2 rounded bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-50"
              >
                <Send size={16} />
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="bg-gray-200" />

      {/* ─────────── 중앙 active gate ─────────── */}
      <div className="flex flex-col h-full overflow-hidden bg-gray-50 p-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-2">
          현재 게이트 {lastGate ? <code className="text-xs text-emerald-700 ml-1">{lastGate}</code> : null}
        </h3>
        {!sid && (
          <div className="text-xs text-gray-500 mt-4">
            좌측에 질문을 입력하면 5단계 흐름이 시작됩니다.<br />
            Phase B 는 scaffold 단계 — Gate I 실제 분류는 Phase C 에서.
          </div>
        )}
        {sid && lastGate === "intent_classified" && (
          <div className="text-xs text-gray-700 bg-amber-50 border border-amber-300 rounded p-3 mt-2">
            <strong>Phase B stub</strong> — intent 분류 + 5종 후보 검색은 Phase C 에서 구현됩니다.<br />
            현재는 세션 생성 + decision_log 기록만 동작합니다.
          </div>
        )}
      </div>

      <div className="bg-gray-200" />

      {/* ─────────── 우측 graph + 7-tab ─────────── */}
      <div className="flex flex-col h-full overflow-hidden bg-white p-3">
        <h3 className="text-sm font-semibold text-gray-700 mb-2">온톨로지 그래프 / 호출 결과</h3>
        <div className="text-xs text-gray-400">
          (Phase F 에서 OntologyGraphMini + 7-tab viewer 가 들어옵니다)
        </div>
      </div>
    </div>
  );
}
