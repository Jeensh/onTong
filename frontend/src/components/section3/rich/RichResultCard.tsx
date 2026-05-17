"use client";

/**
 * agent 의 final.payload (또는 modeling_result.response.result) 를 받아
 * 자동으로 가장 적절한 rich 표시를 선택.
 *
 * 표시 우선순위:
 * 1. summary 강조 헤더 (risk_level 있으면 badge)
 * 2. ontology graph (visualization.nodes/edges)
 * 3. file tree (source_locations / direct_impact.methods)
 * 4. data tables (process_locations / downstream_steps / data_locations / test_cases)
 * 5. matched terms / standards / variables chips
 * 6. cypher / 합성 Python (접힘)
 */

import { AlertTriangle, CheckCircle2, Network, Sigma } from "lucide-react";
import { OntologyGraphSVG } from "../OntologyGraphSVG";
import { DataTable } from "./DataTable";
import { FileTreeView } from "./FileTreeView";
import { CodeBlock } from "./CodeBlock";

interface Props {
  /** AgentFinalPayload — final event 의 payload (호환을 위해 loose 한 any 사용) */
  result?: any;
  /** 강조할 method (예: 변경 대상) */
  highlightMethod?: string;
}

const RISK_TONE: Record<string, string> = {
  HIGH: "bg-red-100 text-red-700 border-red-300",
  MEDIUM: "bg-amber-100 text-amber-700 border-amber-300",
  LOW: "bg-emerald-100 text-emerald-700 border-emerald-300",
  UNKNOWN: "bg-muted text-muted-foreground border-border",
};

export function RichResultCard({ result, highlightMethod }: Props) {
  if (!result) return null;
  const mResult = (result.modeling_response?.result ?? {}) as Record<string, any>;
  const summary = result.summary ?? mResult.summary ?? "";
  const confidence = result.modeling_response?.confidence;
  const riskLevel = mResult.risk_level as string | undefined;
  const riskFactors = (mResult.risk_factors ?? []) as string[];
  const directMethods = (mResult.direct_impact?.methods ?? []) as Array<Record<string, any>>;
  const affectedSteps = (mResult.direct_impact?.affected_steps ?? []) as Array<Record<string, any>>;
  const downstreamSteps = (mResult.indirect_impact?.downstream_steps ?? []) as Array<Record<string, any>>;
  const sourceLocations = (mResult.source_locations ?? []) as Array<Record<string, any>>;
  const processLocations = (mResult.process_locations ?? []) as Array<Record<string, any>>;
  const dataLocations = (mResult.data_locations ?? []) as Array<Record<string, any>>;
  const matchedTerms = (mResult.matched_terms ?? []) as Array<Record<string, any>>;
  const testCases = (mResult.test_cases ?? []) as Array<Record<string, any>>;
  const dataDeps = (mResult.data_dependencies ?? []) as string[];
  const sandboxCases = (result.sandbox_result?.cases ?? []) as Array<Record<string, any>>;

  return (
    <div className="space-y-4">
      {/* ── Header — summary + risk badge ───────────────── */}
      <div className="rounded-xl border-2 border-primary/20 bg-gradient-to-br from-primary/5 via-card to-card p-4">
        <div className="flex items-start gap-3">
          {result.ok !== false ? (
            <div className="flex-shrink-0 w-9 h-9 rounded-lg bg-primary/15 text-primary flex items-center justify-center">
              <CheckCircle2 size={18} />
            </div>
          ) : (
            <div className="flex-shrink-0 w-9 h-9 rounded-lg bg-red-100 text-red-700 flex items-center justify-center">
              <AlertTriangle size={18} />
            </div>
          )}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              {riskLevel && (
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${RISK_TONE[riskLevel] || RISK_TONE.UNKNOWN}`}>
                  {riskLevel}
                </span>
              )}
              {typeof confidence === "number" && (
                <span className="px-2 py-0.5 rounded-full text-[10px] bg-muted border border-border">
                  conf {confidence.toFixed(2)}
                </span>
              )}
            </div>
            <div className="text-sm font-semibold text-foreground mt-1 break-words">{summary}</div>
            {riskFactors.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {riskFactors.map((f, i) => (
                  <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-200">{f}</span>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* matched terms */}
        {matchedTerms.length > 0 && (
          <div className="mt-3 pt-3 border-t border-border/50">
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1.5">매칭 용어</div>
            <div className="flex flex-wrap gap-1.5">
              {matchedTerms.map((t, i) => (
                <span key={i} className="inline-flex items-center gap-1 rounded-full bg-pink-100 text-pink-800 border border-pink-300 px-2 py-0.5 text-[11px]">
                  <strong>{t.korean ?? t.name}</strong>
                  {t.english && <span className="opacity-70 text-[10px]">({t.english})</span>}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ── ontology graph ───────────────────────────────── */}
      {result.visualization?.nodes && result.visualization.nodes.length > 0 && (
        <Section title="🗺 Ontology Graph" subtitle={`${result.visualization.nodes.length} nodes · ${result.visualization.edges?.length ?? 0} edges`} delay={0.05}>
          <OntologyGraphSVG
            nodes={result.visualization.nodes}
            edges={result.visualization.edges ?? []}
            cypher={result.visualization.cypher}
          />
        </Section>
      )}

      {/* ── 코드 파일 트리 ───────────────────────────────── */}
      {(sourceLocations.length > 0 || directMethods.length > 0) && (
        <Section title="📁 스캔된 코드 위치" delay={0.15}>
          <FileTreeView
            sources={sourceLocations}
            methods={directMethods}
            highlightMethod={highlightMethod}
          />
        </Section>
      )}

      {/* ── 영향 받는 Step / process / data 테이블 ────── */}
      {(affectedSteps.length > 0 || downstreamSteps.length > 0 || processLocations.length > 0) && (
        <Section title="🛤 영향 받는 Step" delay={0.25}>
          {affectedSteps.length > 0 && (
            <div className="mb-2">
              <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">직접 영향 (Direct)</div>
              <DataTable rows={affectedSteps} preferredColumns={["step_number", "korean_name"]} />
            </div>
          )}
          {downstreamSteps.length > 0 && (
            <div className="mb-2">
              <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">다운스트림 (Indirect)</div>
              <DataTable rows={downstreamSteps} preferredColumns={["step_number", "korean_name"]} />
            </div>
          )}
          {processLocations.length > 0 && (
            <div>
              <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">프로세스 위치</div>
              <DataTable rows={processLocations} preferredColumns={["step_number", "korean_name", "roles"]} />
            </div>
          )}
        </Section>
      )}

      {/* ── 데이터 위치 ──────────────────────────────────── */}
      {dataLocations.length > 0 && (
        <Section title="🗄 데이터 위치" delay={0.35}>
          <DataTable rows={dataLocations} preferredColumns={["table_name", "standard_code", "schema_name"]} />
        </Section>
      )}

      {/* ── 테스트 케이스 (simulate) ────────────────────── */}
      {testCases.length > 0 && (
        <Section title="🧪 생성된 테스트 케이스" subtitle={`normal/boundary/error 케이스 ${testCases.length}건`} delay={0.45}>
          <DataTable
            rows={testCases}
            preferredColumns={["case_id", "case_type", "input", "expected_output", "description"]}
            renderCell={{
              case_type: (v) => {
                const tone: Record<string, string> = {
                  normal: "bg-emerald-100 text-emerald-700",
                  boundary: "bg-amber-100 text-amber-700",
                  error: "bg-red-100 text-red-700",
                };
                return <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${tone[String(v)] || "bg-muted"}`}>{String(v)}</span>;
              },
              input: (v) => <code className="text-[10px]">{JSON.stringify(v)}</code>,
              expected_output: (v) => <code className="text-[10px]">{JSON.stringify(v)}</code>,
            }}
          />
        </Section>
      )}

      {/* ── sandbox 실행 결과 ──────────────────────────── */}
      {sandboxCases.length > 0 && (
        <Section title="▶ Sandbox 실행 결과" subtitle={`${result.sandbox_result?.ok_count}/${sandboxCases.length} 성공 · ${result.sandbox_result?.matched_count} expected 일치`} delay={0.55}>
          <DataTable
            rows={sandboxCases.map((c) => ({
              case_id: c.case_id,
              case_type: c.case_type,
              ok: c.execution?.ok,
              result: c.execution?.result,
              matched: c.matched_expected,
              elapsed_sec: c.execution?.elapsed_sec,
              error: c.execution?.error,
            }))}
            preferredColumns={["case_id", "case_type", "ok", "matched", "result", "elapsed_sec", "error"]}
            renderCell={{
              case_type: (v) => {
                const tone: Record<string, string> = {
                  normal: "bg-emerald-100 text-emerald-700",
                  boundary: "bg-amber-100 text-amber-700",
                  error: "bg-red-100 text-red-700",
                };
                return <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${tone[String(v)] || "bg-muted"}`}>{String(v)}</span>;
              },
              ok: (v) => v ? <span className="text-emerald-600">✓</span> : <span className="text-red-600">✗</span>,
              matched: (v) => v === null || v === undefined ? <span className="text-muted-foreground">—</span> : v ? <span className="text-emerald-600">✓</span> : <span className="text-amber-600">≠</span>,
            }}
          />
        </Section>
      )}

      {/* ── 데이터 의존성 chips ───────────────────────── */}
      {dataDeps.length > 0 && (
        <Section title="📦 Data dependencies" delay={0.65}>
          <div className="flex flex-wrap gap-1.5">
            {dataDeps.map((d, i) => (
              <span key={i} className="inline-flex items-center gap-1 rounded bg-orange-100 text-orange-800 border border-orange-300 px-2 py-0.5 text-[11px] font-mono">
                <Sigma size={10} />
                {d}
              </span>
            ))}
          </div>
        </Section>
      )}

      {/* ── 합성 Python 코드 ─────────────────────────── */}
      {result.generated_python && (
        <Section title="🐍 합성된 Python 코드" subtitle="modeling 응답 메타만으로 LLM 이 합성 (slab-design 참조 0건)" delay={0.75}>
          <CodeBlock code={result.generated_python} language="python" filename="generated.py" />
        </Section>
      )}

      {/* ── Cypher ───────────────────────────────────── */}
      {result.visualization?.cypher && (
        <Section title="🔎 Cypher (modeling 이 실행)" delay={0.85}>
          <CodeBlock code={result.visualization.cypher} language="cypher" maxHeight={200} showLineNumbers={false} />
        </Section>
      )}

      {/* ── legacy 보강 — modeling graph 가 빈약할 때 채워주는 정보 ── */}
      {result.legacy_enrich && <LegacyEnrichSection enrich={result.legacy_enrich} />}
    </div>
  );
}

function LegacyEnrichSection({ enrich }: { enrich: any }) {
  const src = (enrich.source_code ?? []) as Array<Record<string, any>>;
  const rules = (enrich.business_rules ?? []) as Array<Record<string, any>>;
  const anchors = (enrich.anchors ?? []) as Array<Record<string, any>>;
  const realiz = (enrich.action_realizations ?? []) as Array<Record<string, any>>;
  const callSites = (enrich.call_sites ?? []) as Array<Record<string, any>>;
  const hits = (enrich.search_hits ?? []) as Array<Record<string, any>>;
  const queries = (enrich.queries ?? []) as string[];

  const total = src.length + rules.length + anchors.length + realiz.length + callSites.length + hits.length;
  if (total === 0) return null;

  return (
    <div className="space-y-3 border-t-2 border-dashed border-amber-300 pt-3 mt-4">
      <div className="text-[11px] uppercase tracking-wide text-amber-700 font-bold">
        ⚙️ legacy /api/ontology/* 보강 — modeling graph 가 비어 있을 때 채워주는 정보
      </div>

      {src.length > 0 && (
        <Section title="📜 Java 소스 (body_text)" delay={0.05}>
          {src.map((m, i) => (
            <div key={i} className="mb-3">
              <div className="text-[10px] text-muted-foreground font-mono mb-1">
                {m.method_fqn}{" "}
                {m.line_start && m.line_end && <span className="text-amber-700">(line {m.line_start}–{m.line_end})</span>}
                {m.role && <span className="ml-2 px-1 py-0 rounded bg-blue-100 text-blue-700">{m.role}</span>}
              </div>
              <CodeBlock code={m.body_text ?? ""} language="text" maxHeight={240} showLineNumbers={false} />
            </div>
          ))}
        </Section>
      )}

      {rules.length > 0 && (
        <Section title="📐 비즈니스 룰" subtitle={`${rules.length}건`} delay={0.15}>
          <div className="space-y-2">
            {rules.map((r, i) => (
              <div key={i} className="rounded border border-rose-200 bg-rose-50 p-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <code className="text-[10px] text-rose-700">{r.fqn}</code>
                  {r.severity && (
                    <span className="text-[10px] px-1 py-0 rounded bg-rose-200 text-rose-800">{r.severity}</span>
                  )}
                </div>
                <div className="text-[12px] text-foreground mt-1">{r.statement}</div>
                {(r.operational_history ?? []).length > 0 && (
                  <div className="mt-1.5 text-[10px] text-rose-700">
                    📕 과거 incident:{" "}
                    {(r.operational_history as any[])
                      .map((h) => `${h.incident_id}${h.summary ? ` (${h.summary})` : ""}`)
                      .join(" · ")}
                  </div>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}

      {anchors.length > 0 && (
        <Section title="📍 anchor — 코드 라인 ↔ action slot 매핑" subtitle={`${anchors.length}건`} delay={0.25}>
          <DataTable
            rows={anchors}
            preferredColumns={["line", "anchor_locator", "target_slot", "code_method_fqn"]}
          />
        </Section>
      )}

      {realiz.length > 0 && (
        <Section title="🔗 action → code 매핑" subtitle={`${realiz.length}건`} delay={0.32}>
          <DataTable rows={realiz} preferredColumns={["code_method_fqn", "scope", "confidence", "rationale"]} />
        </Section>
      )}

      {callSites.length > 0 && (
        <Section title="📞 call-sites (의심스러운 호출)" subtitle={`${callSites.length}건`} delay={0.4}>
          <DataTable
            rows={callSites}
            preferredColumns={["callee_simple_name", "line", "needs_user_confirm", "analysis_source"]}
          />
        </Section>
      )}

      {hits.length > 0 && (
        <Section title="🔍 legacy 통합 검색 hits" subtitle={queries.length ? `질의: ${queries.join(", ")}` : `${hits.length}건`} delay={0.5}>
          <DataTable rows={hits} preferredColumns={["kind", "fqn", "label", "score"]} />
        </Section>
      )}
    </div>
  );
}

function Section({ title, subtitle, children, delay = 0 }: { title: string; subtitle?: string; children: React.ReactNode; delay?: number }) {
  return (
    <div className="section3-anim-section" style={{ animationDelay: `${delay}s` }}>
      <div className="flex items-baseline gap-2 mb-1.5">
        <Network size={11} className="text-primary" />
        <h4 className="text-[12px] font-bold text-foreground">{title}</h4>
        {subtitle && <span className="text-[10px] text-muted-foreground">— {subtitle}</span>}
      </div>
      {children}
    </div>
  );
}
