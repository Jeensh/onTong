"use client";

/**
 * 시뮬레이션 에이전트 — chat shell + 3-pane + intent 별 차별 카드.
 * Phase F: 5종 intent (simulate/impact/locate/explain/hypothesis) 마다 다른
 * 중앙·우측 패널 렌더.
 */
import { useEffect, useState } from "react";
import { Workflow, Send, RotateCcw, Loader2, User, Code2, FileSpreadsheet } from "lucide-react";
import { simulationApi, type GraphResponse, type ReplayResponse, type SimulationGate,
  type SuggestedQuestionView, type DetectedTermView } from "@/lib/section3/simulation";
import { IntentCandidateCard } from "./IntentCandidateCard";
import { BundlePreviewCard } from "./BundlePreviewCard";
import { ExecutedResultCard, ResultErrorBoundary } from "./ExecutedResultCard";
// 우측 패널 제거 (2026-05-23 사용자 요구) — chat + 분석 메인. 필요시 다시 import.
import { SessionHistoryPanel } from "./SessionHistoryPanel";

interface Props {
  initialSid: string | null;
  onNewSession: () => void;
  defaultRepoId: string | null;
}

/** fallback hardcoded — backend /suggested_questions 가 비어 있을 때만 사용. */
const FALLBACK_PRESETS: { intent: string; label: string; query: string }[] = [
  { intent: "simulate",   label: "① 주문 1건 Slab 설계 (S1)",
    query: "ORD20260510001 주문으로 Slab 설계 시뮬레이션 돌려줘" },
  { intent: "simulate",   label: "② 두께 변경 후 비교",
    query: "SdThicknessAction 의 결과 두께 230→200mm 로 바꿨을 때 Slab 결과 차이" },
  { intent: "impact",     label: "③ EDGING 사양 변경 영향",
    query: "SD_HSM_EDGING_SPEC 마진을 늘리면 어떤 step·method 가 영향받아?" },
  { intent: "impact",     label: "④ 단중 하한 룰 변경 영향",
    query: "2차 단중 하한을8000→9000kg 으로 바꾸면 어떤 주문이 fail?" },
  { intent: "locate",     label: "⑤ DG104 에러 발생 위치",
    query: "DG104 (HR_MIN_WGT 미발견) 은 어디서 throw 돼?" },
  { intent: "explain",    label: "⑥ A-a 루프 설명",
    query: "Step 8~13 의 A-a inner loop 가 뭐고 어떻게 수렴해?" },
  { intent: "hypothesis", label: "⑦ 조건 변경 시 단중 변화 (sweep)",
    query: "주문의 설계대기량 상한 값을 10kg씩 10번 증가시킬 때마다 Slab 설계 단중값이 어떻게 변해?" },
];

const INTENT_BADGE: Record<string, { color: string; label: string }> = {
  simulate:   { color: "bg-emerald-100 text-emerald-800 border-emerald-300", label: "시뮬레이션" },
  impact:     { color: "bg-amber-100 text-amber-800 border-amber-300",       label: "영향도 분석" },
  locate:     { color: "bg-sky-100 text-sky-800 border-sky-300",             label: "위치 찾기" },
  explain:    { color: "bg-violet-100 text-violet-800 border-violet-300",    label: "설명" },
  hypothesis: { color: "bg-rose-100 text-rose-800 border-rose-300",          label: "가설 검증" },
  ambiguous:  { color: "bg-gray-100 text-gray-700 border-gray-300",          label: "의도 확인 필요" },
};

export function SimulationChat({ initialSid, onNewSession, defaultRepoId }: Props) {
  const [sid, setSid] = useState<string | null>(initialSid);
  const [repo] = useState<string>(defaultRepoId ?? "slab-design-real-v2");
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastGate, setLastGate] = useState<SimulationGate | null>(null);
  const [replay, setReplay] = useState<ReplayResponse | null>(null);
  const [presets, setPresets] = useState<SuggestedQuestionView[] | null>(null);
  const [detectedTerms, setDetectedTerms] = useState<DetectedTermView[]>([]);
  const [presetSeed, setPresetSeed] = useState(0);
  const [presetCat, setPresetCat] = useState<string>("simulate");

  // 결과 승인 lift up — 왼쪽 turn 카드(③ 결과 도출 완료)도 승인 후에만 표시
  const [executedApproved, setExecutedApproved] = useState(false);
  // 새 session 시작 시 reset
  useEffect(() => { setExecutedApproved(false); }, [sid]);

  // perspective: 현업(business) = 코드 카드/Java 본문 hide, 데이터·답변 중심.
  //              IT(it) = 기존 default, 코드 + 데이터 + 디버그 모두.
  const [perspective, setPerspective] = useState<"business" | "it">(() => {
    if (typeof window === "undefined") return "it";
    return (localStorage.getItem("sim:perspective") as "business" | "it") ?? "it";
  });
  // result_mode — 답변에서 데이터만 / 코드+데이터 (perspective=it 일 때만 의미)
  const [resultMode, setResultMode] = useState<"auto" | "data_only" | "code_and_data">(() => {
    if (typeof window === "undefined") return "auto";
    return (localStorage.getItem("sim:resultMode") as "auto" | "data_only" | "code_and_data") ?? "auto";
  });
  useEffect(() => {
    if (typeof window !== "undefined") localStorage.setItem("sim:perspective", perspective);
  }, [perspective]);
  useEffect(() => {
    if (typeof window !== "undefined") localStorage.setItem("sim:resultMode", resultMode);
  }, [resultMode]);

  // perspective=business 일 때 result_mode 는 자동으로 data_only
  const effectiveResultMode: "data_only" | "code_and_data" = perspective === "business"
    ? "data_only"
    : (resultMode === "data_only" ? "data_only" : "code_and_data");

  // backend 의 동적 예시 질문 로드
  useEffect(() => {
    simulationApi.suggestedQuestions(presetSeed)
      .then(setPresets)
      .catch(() => setPresets(null));
  }, [presetSeed]);

  // query 변경 시 200ms debounce 후 term_lookup
  useEffect(() => {
    if (!query.trim() || sid) {
      setDetectedTerms([]);
      return;
    }
    const t = setTimeout(() => {
      simulationApi.termLookup(query).then(setDetectedTerms).catch(() => setDetectedTerms([]));
    }, 250);
    return () => clearTimeout(t);
  }, [query, sid]);

  useEffect(() => {
    if (!initialSid) return;
    simulationApi.replay(initialSid).then(setReplay).catch((e) => {
      setError(`replay 실패: ${String(e)}`);
    });
  }, [initialSid]);

  async function _refresh(sidToUse: string) {
    const r = await simulationApi.replay(sidToUse);
    setReplay(r);
    setSid(sidToUse);
  }

  async function _onStart() {
    if (!query.trim() || busy) return;
    setBusy(true); setError(null);
    try {
      const r = await simulationApi.start({ user_query: query, repo_id: repo });
      setLastGate(r.next_gate);
      await _refresh(r.session_id);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function _onAction(action: string, opts: { selectedIndex?: number; intent?: string } = {}) {
    if (!sid || !replay || !replay.decisions.length || busy) return;
    setBusy(true); setError(null);
    try {
      const lastTurn = replay.decisions[replay.decisions.length - 1].turn_no;
      const r = await simulationApi.respond(sid, {
        turn_no: lastTurn,
        user_response: {} as unknown as Record<string, unknown>,
        // workaround: API 에 직접 펴서 보냄 (RespondRequest schema)
      } as never);
      // 위 helper 가 union 안 받아서 fetch 직접:
      void r;
    } finally {
      setBusy(false);
    }
  }

  // 직접 fetch — RespondRequest 의 action 필드 그대로 보냄
  async function _onActionDirect(
    action: string,
    extras: Record<string, unknown> = {},
  ) {
    if (!sid || !replay || !replay.decisions.length || busy) return;
    setBusy(true); setError(null);
    try {
      const lastTurn = replay.decisions[replay.decisions.length - 1].turn_no;
      const r = await fetch(`/api/section3/simulation/respond/${sid}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ turn_no: lastTurn, action, ...extras }),
      });
      if (!r.ok) {
        const txt = await r.text().catch(() => "");
        throw new Error(`API ${r.status}: ${txt}`);
      }
      const j = await r.json();
      setLastGate(j.next_gate);
      await _refresh(sid);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  function _onReset() {
    setSid(null); setReplay(null); setLastGate(null); setQuery(""); setError(null);
    onNewSession();
  }

  // 재생성 — 같은 user_query 로 새 세션 생성 (status=done 세션에 rerun 불가 문제 해결)
  async function _onRegenerate() {
    if (busy) return;
    const lastQuery = replay?.user_query;
    if (!lastQuery) return;
    setBusy(true); setError(null);
    try {
      const r = await simulationApi.start({ user_query: lastQuery, repo_id: repo });
      setLastGate(r.next_gate);
      await _refresh(r.session_id);
    } catch (e) {
      setError(`재생성 실패: ${String(e)}`);
    } finally {
      setBusy(false);
    }
  }

  // 가장 최근 게이트 결정
  const lastDecision = replay?.decisions?.[replay.decisions.length - 1] ?? null;
  const intent: string | null =
    replay?.intent ?? (lastDecision?.payload?.intent as string | undefined) ?? null;
  const intentBadge = intent ? INTENT_BADGE[intent] : null;

  return (
    <div className="h-full grid" style={{ gridTemplateColumns: "35% 1px 65%" }}>
      {/* ─────────── 좌측 chat ─────────── */}
      <div className="flex flex-col h-full overflow-hidden bg-white">
        <div className="px-3 py-2 border-b border-gray-200 flex items-center gap-1.5 flex-wrap">
          <Workflow size={15} className="text-emerald-600 flex-shrink-0" />
          <strong className="text-xs flex-shrink-0">시뮬레이션 에이전트</strong>
          {intentBadge && (
            <span className={`text-[10px] px-1.5 py-0.5 rounded border flex-shrink-0 ${intentBadge.color}`}>
              {intentBadge.label}
            </span>
          )}
          {/* perspective toggle (현업 / IT) */}
          <div className="ml-auto flex items-center gap-0.5 bg-gray-100 rounded p-0.5 text-[10.5px] flex-shrink-0">
            <button
              onClick={() => setPerspective("business")}
              className={"px-2 py-0.5 rounded flex items-center gap-1 transition " + (
                perspective === "business"
                  ? "bg-white shadow text-emerald-700 font-semibold"
                  : "text-gray-500 hover:text-gray-700"
              )}
              title="현업 모드 — 데이터·결과 중심, 코드 카드 숨김"
            >
              <User size={11} /> 현업
            </button>
            <button
              onClick={() => setPerspective("it")}
              className={"px-2 py-0.5 rounded flex items-center gap-1 transition " + (
                perspective === "it"
                  ? "bg-white shadow text-violet-700 font-semibold"
                  : "text-gray-500 hover:text-gray-700"
              )}
              title="IT 모드 — 코드 + 데이터 + 디버그 모두 표시"
            >
              <Code2 size={11} /> IT
            </button>
          </div>
          {/* IT 모드일 때만 result_mode chip 노출 */}
          {perspective === "it" && (
            <div className="flex items-center gap-0.5 bg-gray-100 rounded p-0.5 text-[10px] flex-shrink-0">
              {[
                { id: "auto", label: "자동" },
                { id: "data_only", label: "데이터" },
                { id: "code_and_data", label: "코드+데이터" },
              ].map((m) => (
                <button
                  key={m.id}
                  onClick={() => setResultMode(m.id as "auto" | "data_only" | "code_and_data")}
                  className={"px-1.5 py-0.5 rounded transition whitespace-nowrap " + (
                    resultMode === m.id
                      ? "bg-white shadow text-gray-900 font-semibold"
                      : "text-gray-500 hover:text-gray-700"
                  )}
                >
                  {m.label}
                </button>
              ))}
            </div>
          )}
          {/* repo 라벨 — 좁을 때 다음 줄로 wrap, basis-full 로 강제 줄바꿈 */}
          <span className="text-[10px] text-gray-400 basis-full text-right truncate" title={repo}>
            {repo}
          </span>
        </div>

        <SessionHistoryPanel
          currentSid={sid}
          onPick={(picked) => { setSid(picked); _refresh(picked); }}
        />

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {!sid && (() => {
            const allQs = presets ?? FALLBACK_PRESETS.map((p) => ({ ...p, rationale: "", grounded_terms: [] }));
            const byCat: Record<string, typeof allQs> = {};
            for (const q of allQs) (byCat[q.intent] ||= []).push(q);
            const CATS: { id: string; label: string; emoji: string; desc: string }[] = [
              { id: "simulate",   label: "시뮬레이션",  emoji: "🧪", desc: "주문/액션을 실제 돌려보고 결과 확인" },
              { id: "impact",     label: "영향도 분석", emoji: "⚡", desc: "기준/로직 변경 시 영향 범위 추적" },
              { id: "locate",     label: "위치 찾기",   emoji: "🔍", desc: "코드/룰의 정확한 파일·라인" },
              { id: "explain",    label: "설명",        emoji: "💬", desc: "도메인 용어/로직의 자연어 답변" },
              { id: "hypothesis", label: "가설 검증",   emoji: "🔮", desc: "신규 X 추가/변경 시 결과 추론" },
            ];
            const catQs = byCat[presetCat] ?? [];
            return (
              <div className="text-sm text-gray-500 leading-relaxed">
                {/* 카테고리 탭 */}
                <div className="flex flex-wrap gap-1 mb-3">
                  {CATS.map((c) => {
                    const n = byCat[c.id]?.length ?? 0;
                    const active = c.id === presetCat;
                    return (
                      <button
                        key={c.id}
                        onClick={() => setPresetCat(c.id)}
                        className={
                          "px-2 py-1.5 rounded border text-xs flex items-center gap-1 transition " +
                          (active
                            ? "border-emerald-500 bg-emerald-50 text-emerald-800 font-semibold"
                            : "border-gray-200 text-gray-600 hover:border-emerald-300 hover:bg-emerald-50/40")
                        }
                        title={c.desc}
                      >
                        <span>{c.emoji}</span>
                        <span>{c.label}</span>
                        {n > 0 && <span className="text-[9px] px-1 rounded bg-gray-100 text-gray-600">{n}</span>}
                      </button>
                    );
                  })}
                </div>
                <div className="flex items-center justify-between mb-2 text-[10px]">
                  <span className="text-gray-500">
                    {CATS.find((c) => c.id === presetCat)?.desc}
                  </span>
                  <button
                    onClick={() => setPresetSeed((s) => s + 1)}
                    className="text-gray-400 hover:text-emerald-700"
                    title="다른 예시 set"
                  >
                    ↻ 다른 예시
                  </button>
                </div>
                <ul className="mt-1 space-y-1.5">
                  {catQs.length === 0 && (
                    <li className="text-[11px] text-gray-400 italic">이 카테고리의 예시가 없습니다 — ↻ 다른 예시</li>
                  )}
                  {catQs.map((q) => (
                    <li key={q.query}>
                      <button
                        onClick={() => setQuery(q.query)}
                        className="text-left text-xs px-2 py-1.5 rounded border border-gray-200 hover:border-emerald-500 hover:bg-emerald-50 w-full"
                      >
                        <span className="text-gray-400 mr-1.5">{q.label}</span>
                        <span className="text-gray-800">{q.query.length > 100 ? q.query.slice(0, 100) + "..." : q.query}</span>
                        {q.grounded_terms.length > 0 && (
                          <div className="mt-1 flex flex-wrap gap-1">
                            {q.grounded_terms.slice(0, 3).map((t) => (
                              <span key={t.term_fqn} className="text-[9px] px-1 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                                {t.token}→{t.label}
                              </span>
                            ))}
                          </div>
                        )}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })()}

          {/* 사용자 입력 중 ontology 용어 매핑 hint — 한 줄로 간략, 우측 패널 언급 없음 */}
          {!sid && detectedTerms.length > 0 && (
            <div className="text-[10px] flex items-center gap-1 text-fuchsia-700">
              <span className="animate-pulse">🎯</span>
              <span>{detectedTerms.length}개 ontology 용어 감지: {detectedTerms.slice(0, 3).map((t) => t.label).join(", ")}{detectedTerms.length > 3 && " …"}</span>
            </div>
          )}

          {replay?.user_query && (
            <div className="text-xs">
              <div className="text-gray-400 mb-1">사용자</div>
              <div className="bg-emerald-50 border border-emerald-200 rounded p-2 text-sm">
                {replay.user_query}
              </div>
            </div>
          )}

          {replay?.decisions.map((d) => {
            // 2026-05-25: executed turn 카드는 결과 승인 전엔 hide (사용자 요구)
            if (d.gate_kind === "executed" && !executedApproved) return null;
            const stepMeta = _stepMetaForGate(d.gate_kind, d.payload);
            return (
              <div key={d.turn_no} className="text-[12px]">
                <div className={"rounded-lg border-2 p-2.5 " + stepMeta.boxCls}>
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className={"w-6 h-6 rounded-full flex items-center justify-center text-sm font-bold " + stepMeta.badgeCls}>
                      {d.turn_no}
                    </span>
                    <span className={"text-[13.5px] font-bold " + stepMeta.titleCls}>
                      {stepMeta.title}
                    </span>
                  </div>
                  <div className="text-[11.5px] text-gray-700 pl-8 leading-relaxed">
                    {_renderTurnSummary(d.gate_kind, d.payload)}
                  </div>
                </div>
              </div>
            );
          })}

          {busy && (
            <div className="flex items-center gap-2 text-xs text-emerald-700">
              <Loader2 size={14} className="animate-spin" /> agent 진행 중...
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
              placeholder="질문을 입력하세요 (Enter 전송)..."
              rows={2}
              disabled={busy || !!sid}
              className="flex-1 text-sm bg-white border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-1 focus:ring-emerald-500 resize-none disabled:bg-gray-50"
            />
            {sid ? (
              <button onClick={_onReset} className="p-2 rounded border border-gray-300 hover:bg-gray-50" title="새 세션">
                <RotateCcw size={16} />
              </button>
            ) : (
              <button
                onClick={_onStart} disabled={busy || !query.trim()}
                className="p-2 rounded bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-50"
              >
                <Send size={16} />
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="bg-gray-200" />

      {/* ─────────── 중앙 active gate (intent 별 차별) — overflow-y-auto 로 카드 잘림 방지 ─────────── */}
      <div className="flex flex-col h-full overflow-y-auto bg-gray-50 p-4 simulation-middle-panel">
        {!sid && (
          <div className="text-xs text-gray-500 mt-4">
            좌측에 질문을 입력하면 의도 분석 + 후보 카드가 여기에 표시됩니다.
          </div>
        )}

        {lastDecision?.gate_kind === "target_selected" && (
          <IntentCandidateCard
            payload={lastDecision.payload}
            onSelect={(idx) => _onActionDirect("select_candidate", { selected_index: idx })}
            onRequestOther={() => _onActionDirect("request_other")}
            onClarify={(intent) => _onActionDirect("clarify_intent", { intent })}
            onAbort={() => _onActionDirect("abort")}
            busy={busy}
          />
        )}

        {lastDecision?.gate_kind === "bundle_prepared" && (
          <BundlePreviewCard
            payload={lastDecision.payload}
            onConfirm={() => _onActionDirect("confirm_bundle")}
            onCompare={(overrides) => _onActionDirect("compare_with_overrides", { overrides })}
            onAbort={() => _onActionDirect("abort")}
            busy={busy}
          />
        )}

        {lastDecision?.gate_kind === "executed" && (
          <ResultErrorBoundary name="ExecutedResultCard">
            <ExecutedResultCard
              payload={lastDecision.payload}
              intent={(intent as string) ?? "unknown"}
              onRerun={_onRegenerate}
              onNew={_onReset}
              busy={busy}
              perspective={perspective}
              resultMode={effectiveResultMode}
              sessionId={sid ?? undefined}
              approved={executedApproved}
              onApproveChange={setExecutedApproved}
            />
          </ResultErrorBoundary>
        )}
      </div>

    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// 좌측 chat 안 turn summary
// ─────────────────────────────────────────────────────────────────────────────
function _stepMetaForGate(gateKind: string, payload: Record<string, unknown>) {
  // 사용자 친화 라벨 + 색상
  const intent = String(payload.intent ?? "");
  const INTENT_KO: Record<string, string> = {
    simulate: "시뮬레이션", impact: "영향도 분석", locate: "위치 찾기",
    explain: "설명", hypothesis: "가설 검증", ambiguous: "의도 확인 필요",
  };
  if (gateKind === "target_selected") {
    return {
      title: `① 질문 분석 — ${INTENT_KO[intent] ?? intent}`,
      boxCls: "border-sky-300 bg-sky-50/60",
      badgeCls: "bg-sky-600 text-white",
      titleCls: "text-sky-900",
    };
  }
  if (gateKind === "bundle_prepared") {
    return {
      title: "② 시뮬 입력 준비",
      boxCls: "border-amber-300 bg-amber-50/60",
      badgeCls: "bg-amber-600 text-white",
      titleCls: "text-amber-900",
    };
  }
  if (gateKind === "executed") {
    if (payload.error) {
      return {
        title: "③ 결과 — 오류 발생",
        boxCls: "border-red-300 bg-red-50/60",
        badgeCls: "bg-red-600 text-white",
        titleCls: "text-red-900",
      };
    }
    return {
      title: "③ 결과 도출 완료",
      boxCls: "border-emerald-300 bg-emerald-50/60",
      badgeCls: "bg-emerald-600 text-white",
      titleCls: "text-emerald-900",
    };
  }
  return {
    title: gateKind,
    boxCls: "border-gray-200 bg-gray-50",
    badgeCls: "bg-gray-400 text-white",
    titleCls: "text-gray-800",
  };
}

function _renderTurnSummary(gateKind: string, payload: Record<string, unknown>): React.ReactNode {
  const INTENT_KO: Record<string, string> = {
    simulate: "시뮬레이션 — 주문 → slab 설계",
    impact: "영향도 분석 — 기준값 변경 시 결과 영향",
    locate: "위치 찾기 — 코드 안 위치",
    explain: "설명 — ontology 도메인 답변",
    hypothesis: "가설 검증 — 가상 시나리오",
    ambiguous: "의도가 명확하지 않습니다 — 옵션 선택 필요",
  };
  if (gateKind === "target_selected") {
    const intent = String(payload.intent ?? "");
    const cands = (payload.candidates as unknown[] | undefined) ?? [];
    const detected = (payload._detected_terms as Array<{label?: string}> | undefined) ?? [];
    return (
      <>
        <div>{INTENT_KO[intent] ?? intent}</div>
        {cands.length > 0 && (
          <div className="text-gray-500 mt-0.5">관련 동작 후보 {cands.length}개 추출</div>
        )}
        {detected.length > 0 && (
          <div className="text-fuchsia-700 mt-0.5">
            ontology 용어 {detected.length}개 감지: {detected.slice(0, 3).map((t) => t.label).join(", ")}
            {detected.length > 3 && " …"}
          </div>
        )}
      </>
    );
  }
  if (gateKind === "bundle_prepared") {
    const conf = payload.confidence as number | undefined;
    const fx = (payload.fixtures as unknown[] | undefined)?.length ?? 0;
    return <span>시뮬 데이터 {fx}건 준비 · 자신감 {conf ? `${(conf * 100).toFixed(0)}%` : "?"}</span>;
  }
  if (gateKind === "executed") {
    const kind = payload.kind as string;
    if (payload.error) return <span className="text-red-700">{String(payload.error).slice(0, 120)}</span>;
    const KIND_KO: Record<string, string> = {
      executed_full_design: "slab 21-step 전체 설계 결과",
      executed_impact: "영향받는 method · 주문 · rule 추출 완료",
      executed_lookup: "ontology 기반 답변 합성 완료",
      executed_compare: "변경 전·후 비교 결과",
      executed_hypothesis_workflow: "가설 4-step 워크플로 완료",
      executed_new_standard: "신규 기준 추가 시뮬 완료",
    };
    return <span>{KIND_KO[kind] ?? "실행 완료"}</span>;
  }
  return <code>{gateKind}</code>;
}
