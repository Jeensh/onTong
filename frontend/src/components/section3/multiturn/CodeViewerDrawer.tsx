"use client";

/**
 * Phase 11 — CodeViewerDrawer.
 *
 * Slide-in drawer triggered by clicking a Gate I candidate / Gate III impact
 * affected_method / GateBundle target. Fetches:
 *   - Java body + file_path + line range  (sec2 /code-methods/{fqn}/body)
 *   - Python translation (sec3 /translate)
 *   - Ontology context: action, callers (sec2 endpoints chained)
 * Side-by-side Java/Python with line numbers + ontology relations panel.
 */

import { useEffect, useState } from "react";
import { X, FileCode2, ArrowRight, AlertCircle, Loader2, Users, Tag } from "lucide-react";

interface Props {
  open: boolean;
  fqn: string;
  repoId: string;
  /** optional pre-fetched body to skip API call */
  preloadedBody?: string | null;
  /** location preview (file_path / line_start / line_end) — optional */
  location?: { file_path: string; line_start: number; line_end: number } | null;
  /** optional preview of Python (e.g. from GateBundle) — skip translate call */
  preloadedPython?: string | null;
  onClose: () => void;
}

interface BodyResponse {
  fqn: string;
  body_text: string;
  line_start: number;
  line_end: number;
  return_type: string;
}

interface CallerRow {
  fqn: string;
  match_kind?: string;
  strength?: number;
  via?: string;
}

export function CodeViewerDrawer({
  open, fqn, repoId, preloadedBody, location, preloadedPython, onClose,
}: Props) {
  const [body, setBody] = useState<BodyResponse | null>(null);
  const [python, setPython] = useState<string | null>(preloadedPython ?? null);
  const [callers, setCallers] = useState<CallerRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !fqn) return;
    let cancelled = false;
    setLoading(true); setErr(null); setBody(null); setCallers([]);
    if (!preloadedPython) setPython(null);

    const fqnEnc = encodeURIComponent(fqn);
    const repo = encodeURIComponent(repoId || "");

    Promise.all([
      fetch(`/api/ontology/code-methods/${fqnEnc}/body${repo ? `?repo_id=${repo}` : ""}`)
        .then((r) => (r.status === 200 ? r.json() : null)),
      fetch(`/api/ontology/code-methods/${fqnEnc}/callers${repo ? `?repo_id=${repo}` : ""}`)
        .then((r) => (r.status === 200 ? r.json() : { callers: [] })),
    ]).then(([bodyResp, callersResp]) => {
      if (cancelled) return;
      const bodyData: BodyResponse | null = bodyResp && bodyResp.body_text ? bodyResp : null;
      setBody(bodyData);
      setCallers((callersResp?.callers ?? []).slice(0, 30));
      // python translate — only if no pre-loaded
      if (!preloadedPython && bodyData?.body_text) {
        // Optional: call translate via run-custom endpoint indirectly. For
        // now we just leave python null; GateBundle path supplies preloaded.
      }
    }).catch((e) => {
      if (!cancelled) setErr(String(e));
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });

    return () => { cancelled = true; };
  }, [open, fqn, repoId, preloadedPython]);

  if (!open) return null;

  const filePath = body?.fqn
    ? body.fqn.split("(", 1)[0].replace(/\./g, "/") + ".java"
    : (location?.file_path ?? "");

  const lineStart = body?.line_start ?? location?.line_start ?? 0;
  const lineEnd = body?.line_end ?? location?.line_end ?? 0;
  const javaBody = body?.body_text ?? preloadedBody ?? "";

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* backdrop */}
      <button
        className="absolute inset-0 bg-black/30"
        onClick={onClose}
        aria-label="close"
      />
      {/* drawer */}
      <div className="ml-auto w-[min(1200px,90vw)] h-full bg-card border-l border-border shadow-xl flex flex-col">
        {/* header */}
        <div className="px-4 py-3 border-b border-border flex items-center justify-between bg-card sticky top-0">
          <div className="flex items-center gap-2 min-w-0">
            <FileCode2 size={16} className="text-primary shrink-0" />
            <div className="min-w-0">
              <div className="text-sm font-semibold truncate" title={fqn}>
                {fqn}
              </div>
              {lineStart > 0 && (
                <div className="text-[11px] text-muted-foreground font-mono mt-0.5">
                  {filePath}:{lineStart}–{lineEnd}
                </div>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded hover:bg-muted text-muted-foreground"
            aria-label="close"
          >
            <X size={16} />
          </button>
        </div>

        {/* body */}
        <div className="flex-1 overflow-auto p-4 space-y-3">
          {loading && (
            <div className="flex items-center justify-center py-12 text-muted-foreground text-sm">
              <Loader2 size={14} className="animate-spin mr-2" />
              fetching…
            </div>
          )}
          {err && (
            <div className="flex items-start gap-2 p-3 bg-rose-50 border border-rose-200 rounded text-rose-700 text-[12px]">
              <AlertCircle size={14} className="mt-0.5 shrink-0" />
              <div>fetch 실패: {err}</div>
            </div>
          )}

          {/* side-by-side code */}
          {!loading && (javaBody || python) && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <CodePane
                title="Java (legacy)"
                language="java"
                source={javaBody}
                lineStart={lineStart}
                empty="body 없음"
              />
              <CodePane
                title="Python (sim_v2 변환)"
                language="python"
                source={python ?? ""}
                lineStart={1}
                empty="Python 변환 미요청"
              />
            </div>
          )}

          {/* callers — ontology relations */}
          {!loading && callers.length > 0 && (
            <div className="border border-border rounded p-3 bg-muted/20">
              <div className="flex items-center gap-1 text-[11px] font-semibold mb-2">
                <Users size={11} />
                이 메서드를 호출하는 곳 ({callers.length})
              </div>
              <div className="overflow-auto max-h-48 border border-border rounded bg-card">
                <table className="text-[11px] w-full">
                  <thead className="bg-muted/60 sticky top-0">
                    <tr>
                      <th className="px-2 py-1 text-left font-medium">caller fqn</th>
                      <th className="px-2 py-1 text-left font-medium">match</th>
                      <th className="px-2 py-1 text-left font-medium w-14">신뢰</th>
                    </tr>
                  </thead>
                  <tbody>
                    {callers.map((c, i) => (
                      <tr key={`${c.fqn}-${i}`} className="border-t border-border">
                        <td className="px-2 py-1 font-mono truncate max-w-[400px]" title={c.fqn}>
                          {c.fqn}
                        </td>
                        <td className="px-2 py-1 font-mono text-muted-foreground">
                          {c.match_kind ?? c.via ?? "—"}
                        </td>
                        <td className="px-2 py-1 font-mono">
                          {c.strength != null ? Math.round(c.strength * 100) + "%" : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ontology relations placeholder */}
          {!loading && (
            <div className="border border-border rounded p-3 bg-muted/20 text-[11px] text-muted-foreground">
              <div className="flex items-center gap-1 mb-1">
                <Tag size={11} /> 관련 BusinessTerm / Action — onTong ontology 매핑
              </div>
              <div className="text-[10px]">
                (확장 예정: term_resolver, action realizations 표시)
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function CodePane({
  title, language, source, lineStart, empty,
}: {
  title: string;
  language: "java" | "python";
  source: string;
  lineStart: number;
  empty: string;
}) {
  if (!source) {
    return (
      <div className="border border-border rounded p-3 bg-muted/30">
        <div className="text-[11px] font-medium text-muted-foreground mb-1">{title}</div>
        <div className="text-[11px] text-muted-foreground italic">{empty}</div>
      </div>
    );
  }
  const lines = source.split("\n");
  return (
    <div className="border border-border rounded overflow-hidden">
      <div className="bg-muted/50 px-2 py-1 text-[11px] font-medium border-b border-border flex items-center justify-between">
        <span>{title}</span>
        <span className="text-[10px] text-muted-foreground">{lines.length} lines</span>
      </div>
      <pre className="overflow-auto max-h-96 bg-card p-2 text-[11px] leading-relaxed font-mono">
        <code className={`language-${language}`}>
          {lines.map((ln, i) => (
            <div key={i} className="flex">
              <span className="select-none text-muted-foreground/60 pr-3 text-right" style={{ minWidth: 36 }}>
                {lineStart + i}
              </span>
              <span className="whitespace-pre">{ln}</span>
            </div>
          ))}
        </code>
      </pre>
    </div>
  );
}
