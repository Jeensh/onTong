"use client";

/**
 * Phase 11 — Modification Guide panel.
 *
 * 주어진 method 의 "수정하려면 알아야 할 것들" 한 번에 묶어 보여주는 패널.
 * Backend: POST /api/section3/multiturn/modification-guide.
 *
 * 구성:
 *  - 1) 본문 body + line range + return_type
 *  - 2) 호출자 (Phase 10 match_kind / strength)
 *  - 3) W75 idiom rewrites
 *  - 4) W71→W72 quick diagnose (passing/fixtures/stubs)
 *  - 5) 권고 메시지
 */

import { useEffect, useState } from "react";
import { Lightbulb, FileCode2, Users, GitBranch, Activity, Loader2, AlertCircle, ArrowRight } from "lucide-react";

interface CallerRow { fqn: string; match_kind: string | null; strength: number | null; }
interface IdiomRow { idiom_name: string; java_snippet: string; python_snippet: string; }
interface GuideResp {
  method_fqn: string;
  body_text: string;
  line_start: number;
  line_end: number;
  return_type: string;
  callers: CallerRow[];
  idiom_rewrites: IdiomRow[];
  diagnostic_passing: number;
  diagnostic_fixtures: number;
  diagnostic_stubs: number;
  hints: string[];
}

interface Props {
  fqn: string;
  repoId: string;
  open: boolean;
  onClose: () => void;
}

export function ModificationGuidePanel({ fqn, repoId, open, onClose }: Props) {
  const [data, setData] = useState<GuideResp | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !fqn) return;
    let cancelled = false;
    setLoading(true); setErr(null); setData(null);
    fetch("/api/section3/multiturn/modification-guide", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code_method_fqn: fqn, repo_id: repoId }),
    })
      .then((r) => r.json())
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setErr(String(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [open, fqn, repoId]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex">
      <button
        className="absolute inset-0 bg-black/30"
        onClick={onClose}
        aria-label="close"
      />
      <div className="ml-auto w-[min(900px,90vw)] h-full bg-card border-l border-border shadow-xl flex flex-col">
        {/* header */}
        <div className="px-4 py-3 border-b border-border bg-card sticky top-0 flex items-center justify-between">
          <div className="flex items-center gap-2 min-w-0">
            <Lightbulb size={16} className="text-amber-500 shrink-0" />
            <div className="min-w-0">
              <div className="text-sm font-semibold">수정 가이드</div>
              <div className="text-[11px] font-mono text-muted-foreground truncate" title={fqn}>
                {fqn}
              </div>
            </div>
          </div>
          <button onClick={onClose} className="text-[12px] text-muted-foreground hover:text-foreground px-2 py-1">
            닫기
          </button>
        </div>

        <div className="flex-1 overflow-auto p-4 space-y-4">
          {loading && (
            <div className="flex items-center justify-center py-12 text-muted-foreground text-sm">
              <Loader2 size={14} className="animate-spin mr-2" />
              온톨로지 + sim_v2 데이터 모으는 중…
            </div>
          )}
          {err && (
            <div className="flex items-start gap-2 p-3 bg-rose-50 border border-rose-200 rounded text-rose-700 text-[12px]">
              <AlertCircle size={14} className="mt-0.5 shrink-0" />
              {err}
            </div>
          )}

          {data && (
            <>
              {/* 1. 본문 메타 */}
              <Section icon={<FileCode2 size={12} />} title="대상 method">
                <div className="grid grid-cols-3 gap-3 text-[11px]">
                  <Meta label="line range" value={data.line_start > 0 ? `${data.line_start}–${data.line_end}` : "—"} />
                  <Meta label="return type" value={data.return_type || "—"} />
                  <Meta label="body 길이" value={`${data.body_text.length} chars`} />
                </div>
                {data.body_text && (
                  <pre className="text-[10px] font-mono bg-muted/40 rounded mt-2 p-2 overflow-auto max-h-40 whitespace-pre">
{data.body_text.split("\n").slice(0, 12).join("\n")}{data.body_text.split("\n").length > 12 ? "\n…" : ""}
                  </pre>
                )}
              </Section>

              {/* 2. 권고 메시지 */}
              {data.hints.length > 0 && (
                <Section icon={<Lightbulb size={12} />} title={`권고 (${data.hints.length})`}>
                  <ul className="space-y-1.5">
                    {data.hints.map((h, i) => (
                      <li key={i} className="text-[11px] flex items-start gap-2">
                        <span className="text-amber-500 mt-0.5">▸</span>
                        <span>{h}</span>
                      </li>
                    ))}
                  </ul>
                </Section>
              )}

              {/* 3. 호출자 */}
              <Section icon={<Users size={12} />} title={`호출자 (${data.callers.length})`}>
                {data.callers.length === 0 ? (
                  <div className="text-[11px] text-muted-foreground italic">caller_graph 빈 결과 — receiver 부재 또는 dead code</div>
                ) : (
                  <div className="overflow-auto max-h-48 border border-border rounded">
                    <table className="text-[11px] w-full">
                      <thead className="bg-muted sticky top-0">
                        <tr>
                          <th className="px-2 py-1 text-left font-medium">caller fqn</th>
                          <th className="px-2 py-1 text-left font-medium">match_kind</th>
                          <th className="px-2 py-1 text-right font-medium w-14">신뢰</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.callers.slice(0, 30).map((c, i) => (
                          <tr key={`${c.fqn}-${i}`} className="border-t border-border">
                            <td className="px-2 py-1 font-mono truncate max-w-[400px]" title={c.fqn}>{c.fqn}</td>
                            <td className="px-2 py-1 font-mono text-muted-foreground">{c.match_kind ?? "—"}</td>
                            <td className="px-2 py-1 font-mono text-right">
                              {c.strength != null ? Math.round(c.strength * 100) + "%" : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Section>

              {/* 4. Idiom rewrites */}
              <Section icon={<GitBranch size={12} />} title={`W75 Idiom rewrites (${data.idiom_rewrites.length})`}>
                {data.idiom_rewrites.length === 0 ? (
                  <div className="text-[11px] text-muted-foreground italic">매칭된 W75 idiom 없음 — body 가 단순 산술/getter 위주</div>
                ) : (
                  <div className="overflow-auto max-h-48 border border-border rounded">
                    <table className="text-[11px] w-full">
                      <thead className="bg-muted">
                        <tr>
                          <th className="px-2 py-1 text-left font-medium">idiom</th>
                          <th className="px-2 py-1 text-left font-medium">Java</th>
                          <th className="px-2 py-1 w-6"></th>
                          <th className="px-2 py-1 text-left font-medium">Python</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.idiom_rewrites.map((r, i) => (
                          <tr key={i} className="border-t border-border">
                            <td className="px-2 py-1 font-mono text-primary/80">{r.idiom_name}</td>
                            <td className="px-2 py-1 font-mono text-muted-foreground">{r.java_snippet}</td>
                            <td className="px-2 py-1 text-center text-muted-foreground"><ArrowRight size={10} className="inline" /></td>
                            <td className="px-2 py-1 font-mono">{r.python_snippet}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Section>

              {/* 5. Quick diagnose */}
              <Section icon={<Activity size={12} />} title="현재 baseline (수정 후 비교 기준)">
                <div className="grid grid-cols-3 gap-3">
                  <Meta label="fixtures" value={String(data.diagnostic_fixtures)} />
                  <Meta label="passing" value={`${data.diagnostic_passing}/${data.diagnostic_fixtures}`} />
                  <Meta label="stubs 주입" value={String(data.diagnostic_stubs)} />
                </div>
                <div className="text-[10px] text-muted-foreground mt-2">
                  수정 후 [수정 시뮬] 탭에서 동일 fixture 로 재실행하면 동일/diff 즉시 확인 가능.
                </div>
              </Section>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Section({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div className="border border-border rounded p-3 bg-muted/10">
      <div className="flex items-center gap-1.5 text-[11px] font-semibold mb-2">
        {icon} {title}
      </div>
      {children}
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] text-muted-foreground uppercase tracking-wide">{label}</div>
      <div className="text-[12px] font-mono font-medium mt-0.5">{value}</div>
    </div>
  );
}
