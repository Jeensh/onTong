"use client";

import { useState } from "react";
import {
  ArrowRight,
  Bot,
  CheckCircle2,
  Lightbulb,
  Link2,
  Loader2,
  Network,
  Save,
  Search,
  Sparkles,
} from "lucide-react";
import {
  bridgeAssist,
  bridgeTermOverlay,
  bridgeListTerms,
  saveAssistAsScenario,
  type BridgeOverlay,
  type ScenarioDraft,
} from "@/lib/simulation/storageApi";
import { getStepLabel } from "@/lib/simulation/stepLabels";
import { HelpPopover } from "./HelpPopover";
import { JsonTable } from "./JsonTable";

interface Props {
  onHandoffToSandbox?: (stepId: string, presetInputs: Record<string, unknown>) => void;
}

export function OntologyBridgePanel({ onHandoffToSandbox }: Props = {}) {
  const [term, setTerm] = useState("실수율");
  const [overlay, setOverlay] = useState<BridgeOverlay | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [terms, setTerms] = useState<string[]>([]);

  // AI 어시스턴트 상태
  const [nl, setNl] = useState("HR 실수율 0.85로 줄이면 어떤 결과?");
  const [draft, setDraft] = useState<ScenarioDraft | null>(null);
  const [assistLoading, setAssistLoading] = useState(false);
  const [savedId, setSavedId] = useState<string | null>(null);

  const onAssist = async () => {
    if (!nl.trim()) return;
    setAssistLoading(true);
    setErr(null);
    setSavedId(null);
    try {
      const d = await bridgeAssist(nl.trim());
      setDraft(d);
    } catch (e) {
      setErr(String(e));
    } finally {
      setAssistLoading(false);
    }
  };

  const onSaveDraft = async () => {
    if (!draft) return;
    try {
      const saved = await saveAssistAsScenario({
        name: draft.title,
        description: draft.rationale,
        step_id: draft.step_id,
        inputs: draft.inputs,
        tags: draft.tags,
      });
      setSavedId(saved.id);
    } catch (e) {
      setErr(String(e));
    }
  };

  const onSearch = async (q: string) => {
    if (!q.trim()) return;
    setLoading(true);
    setErr(null);
    try {
      const out = await bridgeTermOverlay(q.trim());
      setOverlay(out);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  };

  const onLoadAllTerms = async () => {
    try {
      const r = await bridgeListTerms();
      setTerms(r.items.map((t) => t.canonical));
    } catch (e) {
      setErr(String(e));
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground flex items-center gap-2">
          <Link2 size={20} className="text-primary" />
          온톨로지 브릿지
          <HelpPopover
            title="온톨로지 브릿지 — 무엇을 하는가"
            body={
              <>
                <p>도메인 용어 (실수율 / 두께 / EDGING / PlantMapping...) 를 검색하면 <b>영향받는 step 목록</b> + <b>추천 시나리오</b> 자동 도출.</p>
                <p>한국어 / 영문 / 컬럼명 alias 모두 매칭 (16종 정규화).</p>
                <p>"샌드박스로 →" 버튼으로 추천 inputs 그대로 핸드오프. Section 2 ontology 결합 (graceful timeout fallback).</p>
              </>
            }
          />
        </h1>
        <p className="text-xs text-muted-foreground mt-1">
          도메인 용어 → 영향 받는 sandbox step + 추천 시나리오. Section 2 온톨로지와 결합.
        </p>
      </div>

      {/* AI 어시스턴트 카드 (Phase 7-B) */}
      <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4 space-y-3">
        <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
          <Bot size={16} className="text-amber-600 dark:text-amber-400" />
          AI 시나리오 어시스턴트
          <span className="text-[10px] font-normal text-muted-foreground">자연어 → scenario 자동 변환</span>
        </h3>
        <div className="flex gap-2">
          <input
            type="text"
            value={nl}
            onChange={(e) => setNl(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && onAssist()}
            placeholder='예: "PlantMapping K → CC2 마이그하면?", "포장단중을 10~20으로 좁히면?"'
            className="flex-1 rounded border border-border bg-background px-3 py-2 text-sm"
          />
          <button
            onClick={onAssist}
            disabled={assistLoading}
            className="inline-flex items-center gap-1 rounded bg-amber-600 text-white px-3 py-2 text-sm font-medium hover:bg-amber-700 disabled:opacity-50"
          >
            {assistLoading ? <Loader2 size={14} className="animate-spin" /> : <Bot size={14} />}
            추천 받기
          </button>
        </div>

        {draft && (
          <div className="rounded border border-border bg-card p-3 space-y-2">
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <h4 className="text-sm font-semibold text-foreground">{draft.title}</h4>
                <div className="flex flex-wrap items-center gap-2 mt-0.5 text-[10px]">
                  <span className="text-foreground">{getStepLabel(draft.step_id)}</span>
                  <span className="font-mono text-muted-foreground/70">({draft.step_id})</span>
                  <span className={`rounded px-1.5 py-0.5 ${
                    draft.method === "llm"
                      ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                      : "bg-muted text-muted-foreground"
                  }`}>
                    {draft.method === "llm" ? "LLM 생성" : "Fallback (키워드)"}
                  </span>
                  <span className="text-muted-foreground">신뢰도 {Math.round(draft.confidence * 100)}%</span>
                  {draft.extracted_term && (
                    <span className="text-primary">매칭: {draft.extracted_term}</span>
                  )}
                </div>
              </div>
            </div>
            <p className="text-xs text-muted-foreground">{draft.rationale}</p>
            {draft.tags.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {draft.tags.map((t) => (
                  <span key={t} className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">{t}</span>
                ))}
              </div>
            )}
            <JsonTable data={draft.inputs} caption="시뮬 입력값 (inputs)" maxRows={15} />

            <div className="flex items-center gap-2">
              {onHandoffToSandbox && (
                <button
                  onClick={() => onHandoffToSandbox(draft.step_id, draft.inputs)}
                  className="inline-flex items-center gap-0.5 rounded bg-primary text-primary-foreground px-2 py-1 text-xs font-medium hover:bg-primary/90"
                >
                  <Sparkles size={11} /> 샌드박스로
                </button>
              )}
              <button
                onClick={onSaveDraft}
                disabled={savedId !== null}
                className="inline-flex items-center gap-0.5 rounded border border-border px-2 py-1 text-xs hover:bg-muted disabled:opacity-50"
              >
                {savedId ? <CheckCircle2 size={11} className="text-emerald-600" /> : <Save size={11} />}
                {savedId ? `저장됨 (${savedId.slice(0, 16)})` : "라이브러리에 저장"}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 용어 검색 카드 */}
      <div className="rounded-lg border border-border bg-card p-4 space-y-3">
        <div className="flex gap-2">
          <input
            type="text"
            value={term}
            onChange={(e) => setTerm(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && onSearch(term)}
            placeholder="실수율 / 두께 / EDGING / PlantMapping ..."
            className="flex-1 rounded border border-border bg-background px-3 py-2 text-sm"
          />
          <button
            onClick={() => onSearch(term)}
            disabled={loading}
            className="inline-flex items-center gap-1 rounded bg-primary text-primary-foreground px-3 py-2 text-sm font-medium disabled:opacity-50"
          >
            {loading ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
            검색
          </button>
        </div>

        <div>
          <button
            onClick={onLoadAllTerms}
            className="text-[11px] text-muted-foreground hover:text-foreground underline"
          >
            등록된 용어 모두 보기
          </button>
          {terms.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {terms.map((t) => (
                <button
                  key={t}
                  onClick={() => { setTerm(t); onSearch(t); }}
                  className="rounded border border-border bg-muted/30 px-2 py-0.5 text-[10px] text-muted-foreground hover:bg-muted hover:text-foreground"
                >
                  {t}
                </button>
              ))}
            </div>
          )}
        </div>

        {err && (
          <div className="rounded border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            {err}
          </div>
        )}
      </div>

      {overlay && (
        <>
          <div className="rounded-lg border border-border bg-card p-4 space-y-3">
            <div className="flex items-center gap-2 text-sm">
              <Network size={14} className="text-primary" />
              <span className="font-mono">{overlay.input_term}</span>
              {overlay.canonical && overlay.canonical !== overlay.input_term && (
                <>
                  <ArrowRight size={12} className="text-muted-foreground" />
                  <span className="font-mono text-primary">{overlay.canonical}</span>
                </>
              )}
              {!overlay.matched && (
                <span className="text-xs text-destructive">— 매칭 없음</span>
              )}
            </div>

            <div>
              <p className="text-xs font-medium text-foreground mb-1.5">
                영향 받는 step ({overlay.step_count}건)
              </p>
              <div className="flex flex-wrap gap-1.5">
                {overlay.impacted_steps.map((s) => (
                  <span
                    key={s}
                    className="inline-flex items-center gap-1 rounded border border-primary/30 bg-primary/10 text-primary px-2 py-0.5 text-[11px]"
                    title={s}
                  >
                    <span className="font-medium">{getStepLabel(s)}</span>
                    <span className="font-mono text-[9px] text-primary/60">({s})</span>
                  </span>
                ))}
              </div>
            </div>

            <div className="text-[10px] text-muted-foreground">
              Section 2 온톨로지: {overlay.ontology.available
                ? `available (${overlay.ontology.status})`
                : `unavailable — ${overlay.ontology.reason}`}
            </div>
          </div>

          {overlay.scenario_suggestions.length > 0 && (
            <div className="rounded-lg border border-border bg-card p-4 space-y-3">
              <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
                <Lightbulb size={14} className="text-amber-500" />
                추천 시뮬 시나리오 ({overlay.scenario_suggestions.length}건)
              </h3>
              <div className="space-y-2">
                {overlay.scenario_suggestions.map((s, i) => (
                  <div key={i} className="border border-border rounded p-2.5 space-y-1.5">
                    <div className="flex items-start justify-between gap-2">
                      <h4 className="text-sm font-medium text-foreground">{s.title}</h4>
                      {onHandoffToSandbox && (
                        <button
                          onClick={() => onHandoffToSandbox(s.step_id, s.inputs)}
                          className="inline-flex items-center gap-0.5 rounded bg-primary/10 text-primary px-2 py-0.5 text-[10px] font-medium hover:bg-primary/20 flex-shrink-0"
                        >
                          <Sparkles size={10} /> 샌드박스로
                        </button>
                      )}
                    </div>
                    <p className="text-[11px] text-muted-foreground">{s.rationale}</p>
                    <div className="flex flex-wrap items-center gap-2 text-[10px]">
                      <span className="text-foreground font-medium">{getStepLabel(s.step_id)}</span>
                      <span className="font-mono text-muted-foreground/70">({s.step_id})</span>
                      {s.tags.map((t) => (
                        <span key={t} className="rounded bg-muted px-1 py-0.5 text-muted-foreground">
                          {t}
                        </span>
                      ))}
                    </div>
                    <JsonTable data={s.inputs} caption="시뮬 입력값" maxRows={12} />

                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
