"use client";

/**
 * 감지된 ontology 용어 패널 — 우측 패널 최상단.
 *
 * source 2개:
 *   - 사용자가 좌측 chat 에 입력하는 동안 실시간 term_lookup → `detected`
 *   - /start 응답 payload._detected_terms → `fromSession`
 *
 * "🎯 감지됨" 강조 카드 + pulse animation 으로 시각적으로 확실히 인식.
 */
import { Target, Sparkles } from "lucide-react";
import { type DetectedTermView } from "@/lib/section3/simulation";

interface Props {
  detected: DetectedTermView[];      // realtime
  fromSession: DetectedTermView[];   // server-confirmed
}

export function DetectedTermsPanel({ detected, fromSession }: Props) {
  // dedupe by term_fqn
  const seen = new Set<string>();
  const all: (DetectedTermView & { _source: "live" | "server" })[] = [];
  for (const t of fromSession) {
    if (!seen.has(t.term_fqn)) { seen.add(t.term_fqn); all.push({ ...t, _source: "server" }); }
  }
  for (const t of detected) {
    if (!seen.has(t.term_fqn)) { seen.add(t.term_fqn); all.push({ ...t, _source: "live" }); }
  }
  if (all.length === 0) return null;

  return (
    <div className="border-2 border-fuchsia-300 bg-gradient-to-br from-fuchsia-50 to-purple-50 rounded-lg p-3 shadow-md">
      <div className="flex items-center gap-1.5 mb-2">
        <span className="relative flex h-2.5 w-2.5">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-fuchsia-400 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-fuchsia-600"></span>
        </span>
        <Target size={13} className="text-fuchsia-700" />
        <strong className="text-xs text-fuchsia-900">감지된 ontology 용어</strong>
        <span className="text-[10px] text-fuchsia-700 ml-auto">{all.length} 매칭</span>
      </div>
      <ul className="space-y-1.5">
        {all.slice(0, 8).map((t) => (
          <li key={t.term_fqn} className="bg-white/80 rounded p-1.5 border border-fuchsia-200">
            <div className="flex items-baseline gap-1 flex-wrap">
              <code className="text-[11px] px-1 py-0.5 rounded bg-fuchsia-100 text-fuchsia-900 font-bold">
                {t.token}
              </code>
              <span className="text-[10px] text-gray-400">→</span>
              <span className="text-[11px] font-semibold text-fuchsia-800 inline-flex items-center gap-0.5">
                <Sparkles size={9} /> {t.label}
              </span>
              <code className="text-[9px] text-gray-500 ml-auto font-mono">{t.term_fqn}</code>
            </div>
            {t.definition && (
              <div className="text-[10px] text-gray-700 mt-0.5 leading-relaxed">
                {t.definition.length > 120 ? t.definition.slice(0, 120) + "..." : t.definition}
              </div>
            )}
            {t._source === "server" && (
              <div className="text-[8px] text-fuchsia-600 mt-0.5">✓ 세션 payload 에 grounding 됨</div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
